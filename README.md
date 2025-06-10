# BeautifulSoup

## Installation de MongoDB :
````
# Ubuntu/Debian
sudo apt update
sudo apt install mongodb

# macOS (avec Homebrew)
brew install mongodb-community

# Windows : télécharger depuis https://www.mongodb.com/try/download/community

````

## Démarrer MongoDB :

````
# Linux/macOS
sudo systemctl start mongodb

# ou
mongod

# Windows : démarrer le service MongoDB

````

## Installation Python

### Python 
````
brew install python3
````

### Créer un environnement virtuel 
````
python3 -m venv venv  
````

### Démarrer l'environnement virtuel 
````
# Linux/macOS :
source venv/bin/activate
# Windows :
venv\Scripts\activate
````

##  Installer les dépendances
````
pip install -r requirements.txt
````

## Lancement du script
````
python scraper_bdm.py
````