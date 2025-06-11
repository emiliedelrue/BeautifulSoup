import requests
from bs4 import BeautifulSoup
import pymongo
from datetime import datetime
import re

class BDMScraperDetailed:
    def __init__(self):
        self.base_url = "https://www.blogdumoderateur.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
        try:
            self.client = pymongo.MongoClient("mongodb://localhost:27017/")
            self.db = self.client.blogdumoderateur
            self.collection = self.db.articles
            print("MongoDB connecté")
        except Exception as e:
            print(f" Erreur MongoDB: {e}")

    def get_articles_from_homepage(self, max_articles=5):
        """Récupère les articles depuis la page d'accueil"""
        print(" Récupération des articles...")
        
        try:
            response = self.session.get(self.base_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            articles = soup.select('article')[:max_articles]
            
            article_urls = []
            for article in articles:
                link = article.find('a', href=True)
                if link and link.get('href'):
                    href = link['href']
                    if href.startswith('/'):
                        url = self.base_url + href
                    elif href.startswith('http'):
                        url = href
                    else:
                        continue
                    
                    title = link.get_text().strip()
                    article_urls.append({
                        'url': url,
                        'title_preview': title[:60] + "..." if len(title) > 60 else title
                    })
            
            print(f" {len(article_urls)} articles trouvés\n")
            return article_urls
            
        except Exception as e:
            print(f"Erreur récupération articles: {e}")
            return []

    def scrape_article_detailed(self, url):
        """Scrape un article avec détail des 8 points du TP"""
        print(f" URL: {url}")
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            print(f"  Page chargée ({len(response.content)} caractères)")
            
            article_data = {}
            
            # =================== POINT 1: TITRE ===================
            print(f"\n   POINT 1 - Le titre de l'article:")
            titre = "Titre non trouvé"
            selector = 'h1'  

            title_elem = soup.select_one(selector)
            if title_elem and title_elem.get_text().strip():
                titre = title_elem.get_text().strip()
                print(f"      Trouvé avec '{selector}': {titre}")
            else:
                print(f"      Pas trouvé avec '{selector}'")
            
            article_data['titre'] = titre
            
            # =================== POINT 2: IMAGE PRINCIPAL ===================
            print(f"\n  POINT 2 - L'image principale:")
            image_principale = None
            selector = 'article img'
            
            img = soup.select_one(selector)
            if img and img.get('src'):
                image_principale = img['src']
                print(f"       Trouvé avec '{selector}': {image_principale}")
            else:
                print(f"       Pas trouvé avec '{selector}'")
            
            article_data['image_principale'] = image_principale
            
            # =================== POINT 3: SOUS-CATÉGORIE ===================
            print(f"\n   POINT 3 - La sous-catégorie:")
            sous_categorie = "Non définie"
            selector = 'meta[property="article:tag"]'

            try:
                cats = soup.select_one(selector)
                if cats and cats.get('content'):
                    sous_categorie = cats.get('content').strip()
                    print(f"       Trouvé avec '{selector}': {sous_categorie}")
                else:
                    print(f"       Pas trouvé avec '{selector}'")
            except Exception as e:
                print(f"       Pas trouvé avec '{selector}'")

            article_data['sous_categorie'] = sous_categorie

            # =================== POINT 4: RÉSUMÉ ===================
            print(f"\n   POINT 4 - Le résumé (extrait du champ de l'article):")
            resume = ""
            selector = 'meta[name="description"]'
            
            content = soup.select_one(selector)
            if content and content.get('content'):  
                resume = content.get('content').strip()  
                print(f"       Trouvé avec '{selector}': {resume}")
            else:
                print(f"       Pas trouvé avec '{selector}'")
            
            article_data['resume'] = resume
            
            # =================== POINT 5: DATE DE PUBLICATION ===================
            print(f"\n  POINT 5 - La date de publication:")
            date_publication = datetime.now().strftime('%Y-%m-%d')
            selector = '.entry-date'
            
            date_elem = soup.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text().strip()
                datetime_attr = date_elem.get('datetime')
                
                if datetime_attr:
                    try:
                        date_publication = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                        print(f"      Trouvé avec '{selector}' (datetime): {date_publication}")
                    except:
                        pass

                match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})', date_text)
                if match:
                    day, month, year = match.groups()
                    date_publication = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    print(f"      Trouvé avec '{selector}' (regex): {date_publication}")
                else:
                    print(f"       Trouvé avec '{selector}' mais format non reconnu: '{date_text}'")
            else:
                print(f"       Pas trouvé avec '{selector}'")
            
            article_data['date_publication'] = date_publication
            
            # =================== POINT 6: AUTEUR ===================
            print(f"\n  POINT 6 - L'auteur de l'article:")
            auteur = "Auteur inconnu"
            selector= '.byline'
            
            author = soup.select_one(selector)
            if author and author.get_text().strip():
                auteur = author.get_text().strip()
                print(f"      Trouvé avec '{selector}': {auteur}")
            else:
                print(f"       Pas trouvé avec '{selector}'")
            
            article_data['auteur'] = auteur
            
            # =================== POINT 7: CONTENU NORMALISÉ ===================
            print(f"\n   POINT 7 - Le contenu de l'article (normalisé):")
            selector = 'div.entry-content:not(article img)'
            
            content_elem = soup.select_one(selector) 
            if content_elem and content_elem.get_text().strip():
                contenu = content_elem.get_text().strip()  
                print(f"      Trouvé avec '{selector}': {len(contenu)} caractères")  
            else:
                contenu = ""  
                print(f"       Pas trouvé avec '{selector}'")
            
            article_data['contenu'] = contenu
            
            # =================== POINT 8: DICTIONNAIRE DES IMAGES ===================
            print(f"\n   POINT 8 - Un dictionnaire des images (URL + légende):")
            images = {}
            all_images = soup.find_all('img')
            print(f"       {len(all_images)} images trouvées au total")
            
            for i, img in enumerate(all_images[:5]):  
                src = img.get('src', '')
                alt = img.get('alt', f'Image {i+1}')
                title_attr = img.get('title', '')
                
                if src:
                    if src.startswith('/'):
                        src = self.base_url + src
                    elif not src.startswith('http'):
                        src = self.base_url + '/' + src
                    
                    images[f'image_{i+1}'] = {
                        'url': src,
                        'legende': alt,
                        'title': title_attr
                    }
                    print(f"       Image {i+1}: {alt[:40]}... -> {src[:60]}...")
            
            print(f"     Total images gardées: {len(images)}")
            article_data['images'] = images
            
            # =================== POINT 9: SAUVEGARDE MONGODB ===================
            print(f"\n  POINT 9 - Sauvegarde des données dans une collection MongoDB:")
            
            article_data.update({
                'url': url,
                'date_scraping': datetime.now().isoformat(),
                'nb_images': len(images),
                'longueur_contenu': len(contenu),
                'statut': 'scrape_reussi'
            })
            
            print(f"      Données structurées prêtes pour MongoDB")
            print(f"      Clés: {list(article_data.keys())}")
            
            return article_data
            
        except Exception as e:
            print(f"      Erreur lors du scraping: {e}")
            return None

    def save_to_mongodb(self, article):
        """Sauvegarde en MongoDB avec détails"""
        try:
            existing = self.collection.find_one({'url': article['url']})
            if existing:
                print(f"       Article déjà en base (ID: {existing['_id']})")
                return False
            
            result = self.collection.insert_one(article)
            print(f"      Sauvegardé en MongoDB (ID: {result.inserted_id})")
            return True
            
        except Exception as e:
            print(f"      Erreur MongoDB: {e}")
            return False

    def run_detailed_scraping(self, max_articles=3):
        """Lance le scraping détaillé"""
        print(" DÉBUT DU SCRAPING DÉTAILLÉ BDM")
        print("="*80)
        
        
        articles_info = self.get_articles_from_homepage(max_articles)
        
        if not articles_info:
            print(" Aucun article trouvé")
            return
        
        
        success = 0
        
        for i, article_info in enumerate(articles_info, 1):
            print(f"\n ARTICLE {i}/{len(articles_info)}")
            print(f" Titre aperçu: {article_info['title_preview']}")
            print("─" * 80)
            
            article = self.scrape_article_detailed(article_info['url'])
            
            if article and article['titre'] != "Titre non trouvé":
                if self.save_to_mongodb(article):
                    success += 1
                    print(f"\n      SUCCÈS COMPLET POUR CET ARTICLE!")
                else:
                    print(f"\n      Article scrapé mais pas sauvé (doublon)")
            else:
                print(f"\n      ÉCHEC DU SCRAPING POUR CET ARTICLE")
            


if __name__ == "__main__":
    scraper = BDMScraperDetailed()
    scraper.run_detailed_scraping(max_articles=10)
