import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime
import re
import time
import logging
from urllib.parse import urljoin, urlparse
import random


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
        
        # Vérifier robots.txt
        self.check_robots_txt()

    def check_robots_txt(self):
        """Vérifie le fichier robots.txt"""
        try:
            robots_url = urljoin(self.base_url, '/robots.txt')
            response = self.session.get(robots_url)
            if response.status_code == 200:
                logger.info("Robots.txt récupéré avec succès")
                return response.text
        except Exception as e:
            logger.warning(f"Impossible de récupérer robots.txt: {e}")
        return None

    def inspect_page_structure(self, url=None):
        """Analyse la structure de la page pour debugging"""
        if not url:
            url = self.base_url
        
        response = self.get_page_with_retry(url)
        if not response:
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"\n=== ANALYSE DE LA STRUCTURE DE {url} ===")
        
        # Rechercher tous les types de liens
        all_links = soup.find_all('a', href=True)
        
        print(f"Total de liens trouvés: {len(all_links)}")
        
        # Analyser les patterns d'URLs
        url_patterns = {}
        for link in all_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                # Extraire le pattern de l'URL
                path = urlparse(full_url).path
                
                # Grouper par patterns
                if re.search(r'/\d{4}/\d{2}/\d{2}/', path):
                    pattern = "DATE_ARTICLE"
                elif '/tag/' in path:
                    pattern = "TAG"
                elif '/category/' in path or '/categorie/' in path:
                    pattern = "CATEGORY"
                elif path.count('/') >= 2 and len(path) > 10:
                    pattern = "POTENTIAL_ARTICLE"
                else:
                    pattern = "OTHER"
                
                if pattern not in url_patterns:
                    url_patterns[pattern] = []
                url_patterns[pattern].append(full_url)
        
        # Afficher les résultats
        for pattern, urls in url_patterns.items():
            print(f"\n{pattern}: {len(urls)} URLs")
            for url in urls[:3]:  # Afficher seulement les 3 premiers
                print(f"  - {url}")
            if len(urls) > 3:
                print(f"  ... et {len(urls) - 3} autres")

    def add_random_delay(self, min_delay=1, max_delay=3):
        """Ajoute un délai aléatoire entre les requêtes"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    def get_page_with_retry(self, url, max_retries=3):
        """Récupère une page avec système de retry"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Tentative {attempt + 1}/{max_retries} échouée pour {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Échec définitif pour {url}")
                    return None

    def get_page(self, url):
        """Récupère une page web avec gestion d'erreurs"""
        return self.get_page_with_retry(url)

    def is_article_url(self, url):
        """Détermine si une URL est celle d'un article (version améliorée)"""
        # Exclure les URLs non-articles
        exclude_patterns = [
            r'/page/\d+',
            r'/category/',
            r'/categorie/',
            r'/tag/',
            r'/author/',
            r'/search',
            r'/contact',
            r'/about',
            r'\.jpg$',
            r'\.png$',
            r'\.pdf$',
            r'#',
            r'\?',
            r'/feed',
            r'/rss'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        # Patterns d'articles typiques
        article_patterns = [
            r'/\d{4}/\d{2}/\d{2}/',  # Format date
            r'/\d{4}/\d{2}/',         # Format année/mois
            r'/[^/]+/$',              # Slug d'article
        ]
        
        # L'URL doit avoir un certain format et une certaine longueur
        parsed = urlparse(url)
        path = parsed.path
        
        # Vérifier que le path a une profondeur raisonnable et une longueur minimale
        if (len(path) > 10 and 
            path.count('/') >= 2 and  # Au moins 2 niveaux
            not path.endswith('.html') and  # Eviter les pages statiques
            self.base_url in url):
            return True
        
        return False

    def extract_article_urls(self, page_url=None, max_pages=1):
        """
        Version améliorée pour extraire les URLs d'articles
        """
        if not page_url:
            page_url = self.base_url
            
        all_article_urls = set()  # Utiliser un set pour éviter les doublons
        
        for page in range(1, max_pages + 1):
            if page == 1:
                current_url = page_url
            else:
                # Essayer différents formats de pagination
                pagination_formats = [
                    f"{page_url}/page/{page}",
                    f"{page_url}?page={page}",
                    f"{page_url}/page-{page}"
                ]
                current_url = pagination_formats[0]  # Commencer par le premier format
            
            response = self.get_page(current_url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Stratégie plus large pour trouver les articles
            potential_links = []
            
            # 1. Chercher dans les éléments article
            articles = soup.find_all(['article', 'div'], class_=re.compile(r'(post|article|entry|item)'))
            for article in articles:
                links = article.find_all('a', href=True)
                potential_links.extend(links)
            
            # 2. Chercher des liens avec des classes spécifiques
            specific_selectors = [
                'a[href*="/20"]',  # URLs with year
                '.post-title a',
                '.entry-title a',
                '.article-title a',
                'h1 a, h2 a, h3 a',  # Titles
                '.title a'
            ]
            
            for selector in specific_selectors:
                links = soup.select(selector)
                potential_links.extend(links)
            
            # 3. Fallback: tous les liens
            if not potential_links:
                potential_links = soup.find_all('a', href=True)
            
            # Traiter tous les liens potentiels
            page_articles = 0
            for link in potential_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    
                    # Nettoyer l'URL (supprimer fragments et paramètres)
                    clean_url = full_url.split('#')[0].split('?')[0]
                    
                    if (clean_url not in all_article_urls and 
                        self.base_url in clean_url and
                        self.is_article_url(clean_url)):
                        all_article_urls.add(clean_url)
                        page_articles += 1
            
            logger.info(f"Page {page}: Trouvé {page_articles} nouveaux articles")
            
            # Si aucun article trouvé, essayer une approche différente
            if page_articles == 0 and page == 1:
                logger.info("Aucun article trouvé avec la méthode standard, essai d'une approche alternative...")
                self.inspect_page_structure(current_url)
                
                # Essayer de trouver des articles avec une approche plus permissive
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href')
                    text = link.get_text().strip()
                    
                    if href and text and len(text) > 10:  # Liens avec du texte substantiel
                        full_url = urljoin(self.base_url, href)
                        clean_url = full_url.split('#')[0].split('?')[0]
                        
                        # Critères plus permissifs
                        if (clean_url not in all_article_urls and
                            self.base_url in clean_url and
                            len(urlparse(clean_url).path) > 5 and
                            not any(exclude in clean_url.lower() for exclude in 
                                   ['contact', 'about', 'category', 'tag', 'page/', 'author'])):
                            all_article_urls.add(clean_url)
                            page_articles += 1
                            
                            if page_articles >= 10:  # Limiter pour le test
                                break
                
                logger.info(f"Approche alternative: {page_articles} articles trouvés")
            
            if page_articles == 0:
                break
                
            self.add_random_delay()
        
        article_list = list(all_article_urls)
        logger.info(f"Total: {len(article_list)} URLs d'articles uniques trouvées")
        
        # Afficher quelques exemples pour debugging
        if article_list:
            logger.info("Exemples d'URLs trouvées:")
            for url in article_list[:5]:
                logger.info(f"  - {url}")
        
        return article_list

    def clean_text(self, text):
        """Nettoie et formate le texte"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text.strip())
        text = re.sub(r'[^\w\s\-\.\,\;\:\!\?\(\)\[\]\{\}\"\'àâäéèêëïîôöùûüÿç]', '', text)
        return text

    def extract_date(self, soup):
        """Extrait la date de publication"""
        date_selectors = [
            'time[datetime]',
            '.date',
            '.published',
            '[class*="date"]',
            '[class*="time"]',
            'meta[property="article:published_time"]',
            'meta[name="date"]'
        ]
        
        for selector in date_selectors:
            date_element = soup.select_one(selector)
            if date_element:
                datetime_attr = date_element.get('datetime') or date_element.get('content')
                if datetime_attr:
                    try:
                        dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                        return dt.strftime('%Y-%m-%d')
                    except:
                        pass
                
                date_text = date_element.get_text().strip()
                if date_text:
                    date_patterns = [
                        r'(\d{1,2})/(\d{1,2})/(\d{4})',
                        r'(\d{4})-(\d{1,2})-(\d{1,2})',
                        r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})'
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, date_text)
                        if match:
                            try:
                                if '/' in pattern:
                                    day, month, year = match.groups()
                                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                                elif '-' in pattern:
                                    year, month, day = match.groups()
                                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            except:
                                continue
        
        return datetime.now().strftime('%Y-%m-%d')

    def extract_content(self, soup):
        """Extraction plus précise du contenu"""
        # Supprimer les éléments indésirables
        for unwanted in soup.find_all(['script', 'style', 'nav', 'header', 
                                      'footer', 'sidebar', 'advertisement', 'aside']):
            unwanted.decompose()
        
        # Sélecteurs spécifiques
        content_selectors = [
            '.entry-content',
            '.post-content',
            '.article-content',
            'article .content',
            '.post-body',
            '.article-body',
            'main p',
            'article p'
        ]
        
        content_parts = []
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = self.clean_text(element.get_text())
                if len(text) > 50:
                    content_parts.append(text)
        
        # Fallback: chercher les paragraphes
        if not content_parts:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = self.clean_text(p.get_text())
                if len(text) > 50:
                    content_parts.append(text)
        
        return ' '.join(content_parts) if content_parts else ""

    def extract_metadata(self, soup):
        """Extrait les métadonnées"""
        metadata = {}
        
        # Titre
        title_selectors = ['h1', 'title', '.entry-title', '.post-title', '.article-title']
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                metadata['title'] = self.clean_text(title_element.get_text())
                break
        
        # Description
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description:
            metadata['summary'] = self.clean_text(meta_description.get('content', ''))
        
        # Image
        og_image = soup.find('meta', property='og:image')
        if og_image:
            metadata['thumbnail'] = og_image.get('content', '')
        
        # Auteur
        author_selectors = ['.author', '.by-author', '[class*="author"]']
        for selector in author_selectors:
            author_element = soup.select_one(selector)
            if author_element:
                metadata['author'] = self.clean_text(author_element.get_text())
                break
        
        return metadata

    def scrape_article(self, url):
        """Scrape un article complet"""
        response = self.get_page_with_retry(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extraire les métadonnées
        article_data = self.extract_metadata(soup)
        
        # Ajouter les données de base
        content = self.extract_content(soup)
        article_data.update({
            'url': url,
            'content': content,
            'publication_date': self.extract_date(soup),
            'scraped_at': datetime.now().isoformat(),
            'word_count': len(content.split()) if content else 0
        })
        
        # Validation basique
        if not article_data.get('title') and not content:
            logger.warning(f"Article sans contenu substantiel: {url}")
            return None
            
        return article_data

    def article_exists(self, url):
        """Vérifie si un article existe déjà"""
        return self.collection.count_documents({'url': url}) > 0

    def save_article(self, article_data):
        """Sauvegarde un article"""
        try:
            if self.article_exists(article_data['url']):
                logger.info(f"Article déjà existant: {article_data['url']}")
                return False
            
            result = self.collection.insert_one(article_data)
            logger.info(f"Article sauvegardé: {article_data.get('title', 'Sans titre')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            return False

    def scrape_multiple_articles(self, urls, delay_range=(1, 3)):
        """Scrape plusieurs articles"""
        stats = {
            'total': len(urls),
            'success': 0,
            'failed': 0,
            'already_exists': 0,
            'start_time': datetime.now()
        }
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Scraping article {i}/{len(urls)}: {url}")
            
            if self.article_exists(url):
                stats['already_exists'] += 1
                continue
            
            article_data = self.scrape_article(url)
            
            if article_data and self.save_article(article_data):
                stats['success'] += 1
            else:
                stats['failed'] += 1
            
            if i < len(urls):
                self.add_random_delay(delay_range[0], delay_range[1])
        
        stats['end_time'] = datetime.now()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        return stats

    def get_scraping_stats(self):
        """Statistiques de la base"""
        try:
            total_articles = self.collection.count_documents({})
            return {"total_articles": total_articles}
        except Exception as e:
            logger.error(f"Erreur statistiques: {e}")
            return {}

    def run_full_scraping(self, max_pages=5):
        """Lance un scraping complet"""
        logger.info("Début du scraping complet")
        
        article_urls = self.extract_article_urls(max_pages=max_pages)
        
        if not article_urls:
            logger.warning("Aucune URL d'article trouvée")
            return {"error": "Aucune URL trouvée"}
        
        scraping_stats = self.scrape_multiple_articles(article_urls)
        db_stats = self.get_scraping_stats()
        
        final_stats = {
            "scraping": scraping_stats,
            "database": db_stats
        }
        
        logger.info("Scraping terminé")
        logger.info(f"Résultats: {scraping_stats['success']} succès, {scraping_stats['failed']} échecs")
        
        return final_stats

    def close(self):
        """Ferme les connexions"""
        try:
            self.client.close()
            self.session.close()
            logger.info("Connexions fermées")
        except Exception as e:
            logger.error(f"Erreur fermeture: {e}")


def main():
    """Fonction principale"""
    scraper = BlogDuModerateurScraper()
    
    try:
        # Scraping avec plus de debugging
        stats = scraper.run_full_scraping(max_pages=2)
        print("\n=== RÉSULTATS FINAUX ===")
        print(f"Total articles en base: {stats.get('database', {}).get('total_articles', 0)}")
        if 'scraping' in stats:
            print(f"Articles traités: {stats['scraping'].get('success', 0)}")
            print(f"Articles échoués: {stats['scraping'].get('failed', 0)}")
            print(f"Articles déjà existants: {stats['scraping'].get('already_exists', 0)}")
        
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
