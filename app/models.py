import os
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

from app.utiles import extract_feature, selectors
from config import headers

class Opinion:
    def __init__(self, opinion_id, author, recommendation, stars, content, pros, cons, useful, useless, post_date, purchase_date):
        self.opinion_id = opinion_id
        self.author = author
        self.recommendation = recommendation
        self.content = content
        self.pros = pros
        self.cons = cons
        self.useful = int(useful)
        self.useless = int(useless)
        self.post_date = post_date
        self.purchase_date = purchase_date
        try:
            self.stars = float(stars.split("/")[0].replace(",", "."))
        except (AttributeError, TypeError):
            self.stars = float(stars)

    def to_dict(self):
        return {key: value for key, value in self.__dict__.items()}

class Product:
    def __init__(self, product_id, product_name=None):
        self.product_id = product_id
        self.product_name = product_name
        self.opinions = []
        self.stats = {}

    def extract_opinions(self):
        next_page = f"https://www.ceneo.pl/{self.product_id}#tab=reviews"
        all_opinions_data = []
        
        response = requests.get(next_page, headers=headers)
        if response.status_code != 200:
            return "PRODUCT_NOT_FOUND"
        
        page_dom = BeautifulSoup(response.text, "html.parser")
        self.product_name = extract_feature(page_dom, "h1")
        opinions_count = extract_feature(page_dom, "a.product-review__link > span")

        if not opinions_count:
            return "NO_OPINIONS"

        while next_page:
            print(f"Scraping page: {next_page}")
            response = requests.get(next_page, headers=headers)
            if response.status_code == 200:
                page_dom = BeautifulSoup(response.text, "html.parser")
                opinions = page_dom.select("div.js_product-review:not(.user-post--highlight)")
                
                for opinion_html in opinions:
                    single_opinion = {
                        key: extract_feature(opinion_html, *value)
                        for key, value in selectors.items()
                    }
                    all_opinions_data.append(single_opinion)
                
                try:
                    next_page = "https://www.ceneo.pl" + extract_feature(page_dom, "a.pagination__next", "href")
                except TypeError:
                    next_page = None
            else:
                break
        
        for opinion_data in all_opinions_data:
            self.opinions.append(Opinion(**opinion_data))
        
        return "SUCCESS"

    def process_opinions(self):
        opinions_df = pd.DataFrame([opinion.to_dict() for opinion in self.opinions])
        
        self.stats = {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "opinions_count": opinions_df.shape[0],
            "pros_count": int(opinions_df.pros.astype(bool).sum()),
            "cons_count": int(opinions_df.cons.astype(bool).sum()),
            "pros_cons_count": int((opinions_df.pros.astype(bool) & opinions_df.cons.astype(bool)).sum()),
            "avg_stars": float(opinions_df.stars.mean()),
            "pros": opinions_df.pros.explode().dropna().value_counts().to_dict(),
            "cons": opinions_df.cons.explode().dropna().value_counts().to_dict(),
            "recommendations": opinions_df.recommendation.value_counts(dropna=False).reindex(["Nie polecam", "Polecam", None], fill_value=0).to_dict()
        }

    def save_files(self):
        if not os.path.exists("./app/data"):
            os.mkdir("./app/data")
        if not os.path.exists("./app/data/opinions"):
            os.mkdir("./app/data/opinions")
        if not os.path.exists("./app/data/products"):
            os.mkdir("./app/data/products")
            
        opinions_dict = [opinion.to_dict() for opinion in self.opinions]
        with open(f"./app/data/opinions/{self.product_id}.json", "w", encoding="utf-8") as f:
            json.dump(opinions_dict, f, ensure_ascii=False, indent=4)
            
        with open(f"./app/data/products/{self.product_id}.json", "w", encoding="utf-8") as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=4)

    def load_from_files(self):
         with open(f"./app/data/products/{self.product_id}.json", "r", encoding="utf-8") as f:
            self.stats = json.load(f)
            self.product_name = self.stats.get("product_name")
         with open(f"./app/data/opinions/{self.product_id}.json", "r", encoding="utf-8") as f:
            opinions_data = json.load(f)
            self.opinions = [Opinion(**data) for data in opinions_data]

    def generate_charts(self):
        if not os.path.exists("./app/static/images"):
            os.makedirs("./app/static/images", exist_ok=True)
        
        recommendations = pd.Series(self.stats["recommendations"])
        recommendations.plot.pie(
            label="",
            autopct="%.1f%%",
            title=f"Rozkład rekomendacji o produkcie {self.product_id}",
            labels=["Nie polecam", "Polecam", "Nie mam zdania"],
            colors=["Red", "Green", "LightGray"],
        )
        plt.savefig(f"./app/static/images/{self.product_id}_pie.png")
        plt.close()

        opinions_df = pd.DataFrame([o.to_dict() for o in self.opinions])
        stars_count = opinions_df["stars"].value_counts().sort_index()
        stars_count.plot.bar(
            color="orange",
            figsize=(8, 6),
            title=f"Liczba opinii z poszczególną liczbą gwiazdek dla produktu {self.product_id}"
        )
        plt.xlabel("Liczba gwiazdek")
        plt.ylabel("Liczba opinii")
        plt.tight_layout()
        plt.savefig(f"./app/static/images/{self.product_id}_stars_bar.png")
        plt.close()
