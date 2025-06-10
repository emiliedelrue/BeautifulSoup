import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime
import re
import time
import logging
from urllib.parse import urljoin, urlparse
import json


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlogDuModerateurScraper:
    def __init__(self, mongodb_uri="mongodb://localhost:27017/", db_name="blogdumoderateur"):
        """
        Initialise le scraper
        
        Args:
            mongodb_uri (str): URI de connexion MongoDB
            db_name (str): Nom de la base de données
        """
        self.base_url = "https://www.blogdumoderateur.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Connexion MongoDB
        try:
            self.client = pymongo.MongoClient(mongodb_uri)
            self.db = self.client[db_name]
            self.collection = self.db.articles
            logger.info(f"Connexion MongoDB établie - Base: {db_name}")
        except Exception as e:
            logger.error(f"Erreur connexion MongoDB: {e}")
            raise

    def get_page(self, url):
        """Récupère une page web avec gestion d'erreurs"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de {url}: {e}")
            return None

    def extract_article_urls(self, page_url=None):
        """
        Extrait les URLs des articles depuis la page d'accueil ou une page donnée
        
        Args:
            page_url (str): URL de la page à scraper (par défaut: page d'accueil)
            
        Returns:
            list: Liste des URLs d'articles
        """
        if not page_url:
            page_url = self.base_url
            
        response = self.get_page(page_url)
        if not response:
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        article_urls = []
        
        # Recherche des liens d'articles (adapté à la structure du site)
        article_links = soup.find_all('a', href=True)
        
        for link in article_links:
            href = link.get('href')
            if href and ('article' in href or '/blog/' in href):
                full_url = urljoin(self.base_url, href)
                if full_url not in article_urls and self.base_url in full_url:
                    article_urls.append(full_url)
        
        logger.info(f"Trouvé {len(article_urls)} URLs d'articles")
        return article_urls

    def clean_text(self, text):
        """Nettoie et formate le texte"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    def extract_date(self, soup):
        """Extrait la date de publication au format AAAA-MM-JJ"""
        date_selectors = [
            'time[datetime]',
            '.date',
            '.published',
            '[class*="date"]',
            '[class*="time"]'
        ]
        
        for selector in date_selectors:
            date_element = soup.select_one(selector)
            if date_element:
                datetime_attr = date_element.get('datetime')
                if datetime_attr:
                    try:
                        dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
                
                date_text = date_element.get_text().strip()
                if date_text:
                    date_patterns = [
                        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # JJ/MM/AAAA
                        r'(\d{1,2})-(\d{1,2})-(\d{4})',  # JJ-MM-AAAA
                        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # AAAA-MM-JJ
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, date_text)
                        if match:
                            try:
                                if pattern == r'(\d{4})-(\d{1,2})-(\d{1,2})':
                                    year, month, day = match.groups()
                                else:
                                    day, month, year = match.groups()
                                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            except:
                                continue
        
        return datetime.now().strftime('%Y-%m-%d')  

    def extract_images(self, soup):
        """Extrait les images de l'article avec leurs légendes"""
        images_dict = {}
        images = soup.find_all('img')
        
        for i, img in enumerate(images):
            src = img.get('src') or img.get('data-src')
            if src:
                img_url = urljoin(self.base_url, src)
                
                caption = (
                    img.get('alt') or 
                    img.get('title') or
                    (img.find_next('figcaption').get_text().strip() if img.find_next('figcaption') else '') or
                    ''
                )
                
                images_dict[f"image_{i+1}"] = {
                    "url": img_url,
                    "caption": self.clean_text(caption)
                }
        
        return images_dict

    def scrape_article(self, article_url):
        """
        Scrape un article complet
        
        Args:
            article_url (str): URL de l'article
            
        Returns:
            dict: Données de l'article ou None si erreur
        """
        logger.info(f"Scraping article: {article_url}")
        
        response = self.get_page(article_url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Titre de l'article
        title_selectors = ['h1', '.title', '[class*="title"]', 'title']
        title = ""
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                title = self.clean_text(title_element.get_text())
                break
        
        # 2. Image miniature principale
        thumbnail_selectors = [
            '.featured-image img',
            '.thumbnail img',
            '.hero-image img',
            'article img:first-of-type',
            '.post-thumbnail img'
        ]
        thumbnail = ""
        for selector in thumbnail_selectors:
            thumb_element = soup.select_one(selector)
            if thumb_element:
                src = thumb_element.get('src') or thumb_element.get('data-src')
                if src:
                    thumbnail = urljoin(self.base_url, src)
                    break
        
        # 3. Sous-catégorie
        category_selectors = [
            '.category',
            '.tag',
            '[class*="category"]',
            '.breadcrumb a:last-child',
            'nav a:last-child'
        ]
        subcategory = ""
        for selector in category_selectors:
            cat_element = soup.select_one(selector)
            if cat_element:
                subcategory = self.clean_text(cat_element.get_text())
                break
        
        # 4. Résumé/chapô
        summary_selectors = [
            '.excerpt',
            '.summary',
            '.lead',
            '.chapo',
            '.description',
            'article p:first-of-type'
        ]
        summary = ""
        for selector in summary_selectors:
            summary_element = soup.select_one(selector)
            if summary_element:
                summary = self.clean_text(summary_element.get_text())
                if len(summary) > 50:  # S'assurer que c'est un vrai résumé
                    break
        
        # 5. Date de publication
        publication_date = self.extract_date(soup)
        
        # 6. Auteur
        author_selectors = [
            '.author',
            '.byline',
            '[class*="author"]',
            '[rel="author"]'
        ]
        author = ""
        for selector in author_selectors:
            author_element = soup.select_one(selector)
            if author_element:
                author = self.clean_text(author_element.get_text())
                break
        
        # 7. Contenu de l'article
        content_selectors = [
            '.content',
            '.post-content',
            'article',
            '.entry-content',
            'main'
        ]
        content = ""
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                for unwanted in content_element.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    unwanted.decompose()
                content = self.clean_text(content_element.get_text())
                if len(content) > 200:  
                    break
        
        # 8. Images de l'article
        images = self.extract_images(soup)
        
        article_data = {
            "url": article_url,
            "title": title,
            "thumbnail": thumbnail,
            "subcategory": subcategory,
            "summary": summary,
            "publication_date": publication_date,
            "author": author,
            "content": content,
            "images": images,
            "scraped_at": datetime.now().isoformat()
        }
        
        return article_data

    def save_article(self, article_data):
        """Sauvegarde un article dans MongoDB"""
        try:
            existing = self.collection.find_one({"url": article_data["url"]})
            if existing:
                logger.info(f"Article déjà existant: {article_data['title']}")
                return False
            
            result = self.collection.insert_one(article_data)
            logger.info(f"Article sauvegardé: {article_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    def scrape_multiple_articles(self, max_articles=10):
        """
        Scrape plusieurs articles
        
        Args:
            max_articles (int): Nombre maximum d'articles à scraper
        """
        logger.info(f"Début du scraping de {max_articles} articles")
        
        article_urls = self.extract_article_urls()
        
        if not article_urls:
            logger.warning("Aucun article trouvé")
            return
        
        scraped_count = 0
        for url in article_urls[:max_articles]:
            try:
                article_data = self.scrape_article(url)
                if article_data:
                    if self.save_article(article_data):
                        scraped_count += 1
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erreur lors du scraping de {url}: {e}")
                continue
        
        logger.info(f"Scraping terminé. {scraped_count} nouveaux articles sauvegardés.")

    def get_articles_by_category(self, category):
        """
        Retourne tous les articles d'une catégorie
        
        Args:
            category (str): Nom de la catégorie
            
        Returns:
            list: Liste des articles
        """
        try:
            articles = list(self.collection.find(
                {"subcategory": {"$regex": category, "$options": "i"}},
                {"_id": 0} 
            ))
            logger.info(f"Trouvé {len(articles)} articles dans la catégorie '{category}'")
            return articles
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return []

    def get_all_categories(self):
        """Retourne toutes les catégories disponibles"""
        try:
            categories = self.collection.distinct("subcategory")
            return [cat for cat in categories if cat]  
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des catégories: {e}")
            return []

    def close(self):
        """Ferme la connexion MongoDB"""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("Connexion MongoDB fermée")


def main():
    """Fonction principale"""
    print("=== Scraper Blog du Modérateur ===\n")
    
    try:
        scraper = BlogDuModerateurScraper()
    except Exception as e:
        print(f"Erreur d'initialisation: {e}")
        return
    
    while True:
        print("\nOptions disponibles:")
        print("1. Scraper des articles")
        print("2. Rechercher par catégorie")
        print("3. Afficher toutes les catégories")
        print("4. Quitter")
        
        choice = input("\nVotre choix (1-4): ").strip()
        
        if choice == "1":
            try:
                nb_articles = int(input("Nombre d'articles à scraper (défaut: 5): ") or "5")
                scraper.scrape_multiple_articles(nb_articles)
            except ValueError:
                print("Nombre invalide, utilisation de 5 par défaut")
                scraper.scrape_multiple_articles(5)
        
        elif choice == "2":
            category = input("Nom de la catégorie: ").strip()
            if category:
                articles = scraper.get_articles_by_category(category)
                if articles:
                    print(f"\n=== Articles de la catégorie '{category}' ===")
                    for i, article in enumerate(articles, 1):
                        print(f"\n{i}. {article.get('title', 'Sans titre')}")
                        print(f"   Auteur: {article.get('author', 'Inconnu')}")
                        print(f"   Date: {article.get('publication_date', 'Inconnue')}")
                        print(f"   URL: {article.get('url', '')}")
                        if article.get('summary'):
                            print(f"   Résumé: {article['summary'][:100]}...")
                else:
                    print(f"Aucun article trouvé pour la catégorie '{category}'")
            else:
                print("Nom de catégorie requis")
        
        elif choice == "3":
            categories = scraper.get_all_categories()
            if categories:
                print("\n=== Catégories disponibles ===")
                for i, cat in enumerate(categories, 1):
                    print(f"{i}. {cat}")
            else:
                print("Aucune catégorie trouvée")
        
        elif choice == "4":
            print("Fermeture du programme...")
            break
        
        else:
            print("Choix invalide")
    
    scraper.close()


if __name__ == "__main__":
    main()