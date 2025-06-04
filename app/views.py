from flask import render_template, request, redirect, url_for
from app import app
import requests
from config import headers
from app import utiles
from bs4 import BeautifulSoup
import json
import os
import pandas as pd
import matplotlib.pyplot as plt

import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for matplotlib

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract")
def display_form():
    return render_template("extract.html")

@app.route("/products")
def products():
    products_files = os.listdir("./app/data/products")
    products_list = []
    for filename in products_files:
        with open(f"./app/data/products/{filename}", "r", encoding="UTF-8") as jf:
            product = json.load(jf)
            products_list.append(product)
    return render_template("products.html", products_list=products_list)

@app.route("/extract",methods=['POST'])
def extract():
    product_id = request.form.get('product_id')
    next_page = (f"https://www.ceneo.pl/{product_id}#tab=reviews")
    response = requests.get(next_page,headers=headers)
    if response.status_code == 200:
        page_dom = BeautifulSoup(response.text, "html.parser")
        product_name = utiles.extract_feature(page_dom,"h1")
        opinions_count = utiles.extract_feature(page_dom,"a.product-review__link > span")
        if not opinions_count:
            return render_template("extract.html",error="Dla produktu o podanym ID nie ma jeszcze żadnych opinii.")
    else:
        return render_template("extract.html",error="Nie znaleziono produktu o podanym ID.")
    all_opinions = []
    while next_page:
        print(next_page)
        response = requests.get(next_page,headers=headers)
        if response.status_code == 200:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review:not(.user-post--highlight)")
            for opinion in opinions:
                single_opinion = {
                    key: utiles.extract_feature(opinion,*value)
                    for key, value in utiles.selectors.items()
                }
                all_opinions.append(single_opinion)
            try:
                next_page = "https://www.ceneo.pl" + utiles.extract_feature(page_dom,"a.pagination__next","href")
            except TypeError:
                next_page = None
                print("Brak kolejnej strony.")
        else:
            print(f"{response.status_code}")
    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")
    
    if not os.path.exists("./app/data/opinions"):
        os.mkdir("./app/data/opinions")
        
    with open (f"./app/data/opinions/{product_id}.json","w",encoding="utf-8") as file:
        json.dump(all_opinions,file,ensure_ascii=False,indent=4)
    
    
    opinions = pd.DataFrame.from_dict(all_opinions)
    opinions.stars = opinions.stars.apply(lambda s: s.split("/")[0].replace(",",".")).astype(float)
    opinions.useful = opinions.useful.astype(int)
    opinions.useless = opinions.useless.astype(int)
    stats = {
        "product_id": product_id,
        "product_name": product_name,
        "opinions_count": opinions.shape[0],
        "pros_count": int(opinions.pros.astype(bool).sum()),
        "cons_count": int(opinions.cons.astype(bool).sum()),
        "pros_cons_count": int((opinions.pros.astype(bool) & opinions.cons.astype(bool)).sum()),
        "avg_stars": float(opinions.stars.mean()),
        "pros": opinions.pros.explode().dropna().value_counts().to_dict(),
        "cons": opinions.cons.explode().dropna().value_counts().to_dict(),
        "recommendations": opinions.recommendation.value_counts(dropna=False).reindex(["Nie polecam", "Polecam", None], fill_value=0).to_dict()
    }
    # stats = {
    #     "opinions_count": opinions.shape[0],
    #     "pros_count": int(opinions.pros.astype(bool).sum()),
    #     "cons_count": int(opinions.cons.astype(bool).sum()),
    #     "pros_cons_count"
    #     "pros": opinions.pros.explode().dropna().value_counts(),
    #     "cons": opinions.cons.explode().dropna().value_counts(),
    #     "recommendations": opinions.recommendation.value_counts(dropna=False).reindex(["Nie polecam", "Polecam", None], fill_value=0)
    # }
    
    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")
    if not os.path.exists("./app/data/products"):
        os.mkdir("./app/data/products")
    with open (f"./app/data/products/{product_id}.json","w",encoding="utf-8") as file:
        json.dump(stats,file,ensure_ascii=False,indent=4)
    return redirect(url_for('product', product_id=product_id, product_name=product_name))


@app.route("/author")
def author():
    return render_template("author.html")

@app.route("/product/<product_id>")
def product(product_id):
    #product_name = request.args.get("product_name")
    #opinions = pd.read_json(f"./app/data/opinions/{product_id}.json")
    product_name=request.args.get('product_name')
    with open(f"./app/data/opinions/{product_id}.json", "r", encoding="UTF-8") as jf:
        opinions = json.load(jf)
    return render_template("product.html", product_id=product_id, product_name=product_name, opinions=opinions) 
   


@app.route('/charts/<product_id>')
def charts(product_id):
    if not os.path.exists("./app/static/images"):
        os.mkdir("./app/static/images")
    if not os.path.exists("./app/static/images/charts"):
        os.mkdir("./app/static/images/charts")
    with open(f"./app/data/products/{product_id}.json", "r", encoding="utf-8") as readfile:
        stats = json.load(readfile)
        recommendations = pd.Series(stats["recommendations"])
        recommendations.plot.pie(
            label = "",
            autopct="%.1f%%",
            title= f"Rozkład rekomendacji o produkcie {product_id}",
            labels = ["Nie polecam", "Polecam", "Nie mam zdania"],
            colors = ["Red", "Green", "LightGray"],
        )
    plt.savefig(f"./app/static/images/{stats['product_id']}_pie.png")
    plt.close()

    with open(f"./app/data/opinions/{product_id}.json", "r", encoding="utf-8") as jf:
        opinions = pd.read_json(jf)
        stars_count = opinions["stars"].value_counts().sort_index()
        stars_count.plot.bar(
            color="orange",
            figsize=(8, 6),
            title=f"Liczba opinii z poszczególną liczbą gwiazdek dla produktu {product_id}"
        )
        plt.xlabel("Liczba gwiazdek")
        plt.ylabel("Liczba opinii")
        plt.tight_layout()
        plt.savefig(f"./app/static/images/{product_id}_stars_bar.png")
        plt.close()

    return render_template("charts.html",product_id=product_id, product_name=stats['product_name'])