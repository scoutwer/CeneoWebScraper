from flask import render_template, request, redirect, url_for, send_file
from app import app
from app.models import Product
import os
import json
import pandas as pd
import io
import matplotlib

matplotlib.use('Agg')  

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract")
def display_form():
    return render_template("extract.html")

@app.route("/extract", methods=['POST'])
def extract():
    product_id = request.form.get('product_id')
    product = Product(product_id)
    
    status = product.extract_opinions()
    if status == "PRODUCT_NOT_FOUND":
        return render_template("extract.html", error="Nie znaleziono produktu o podanym ID.")
    if status == "NO_OPINIONS":
        return render_template("extract.html", error="Dla produktu o podanym ID nie ma jeszcze żadnych opinii.")

    product.process_opinions()
    product.save_files()
    
    return redirect(url_for('product', product_id=product.product_id, product_name=product.product_name))


@app.route("/products")
def products():
    if not os.path.exists("./app/data/products"):
        return render_template("products.html", products_list=[])
    products_files = os.listdir("./app/data/products")
    products_list = []
    for filename in products_files:
        with open(f"./app/data/products/{filename}", "r", encoding="UTF-8") as jf:
            product_data = json.load(jf)
            products_list.append(product_data)
    return render_template("products.html", products_list=products_list)

@app.route("/author")
def author():
    return render_template("author.html")

@app.route("/product/<product_id>")
def product(product_id):
    product_name = request.args.get('product_name')
    opinions_path = f"./app/data/opinions/{product_id}.json"
    if not os.path.exists(opinions_path):
         return redirect(url_for('extract')) 
    with open(opinions_path, "r", encoding="UTF-8") as jf:
        opinions = json.load(jf)
    return render_template("product.html", product_id=product_id, product_name=product_name, opinions=opinions)

@app.route('/charts/<product_id>')
def charts(product_id):
    product = Product(product_id)
    product.load_from_files()
    product.generate_charts()
    return render_template("charts.html", product_id=product_id, product_name=product.product_name)

@app.route('/download/<product_id>/<filetype>')
def download(product_id, filetype):
    opinions_path = f"./app/data/opinions/{product_id}.json"
    df = pd.read_json(opinions_path)

    if filetype == "json":
        return send_file(f"data/opinions/{product_id}.json", as_attachment=True)
    elif filetype == "csv":
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        return send_file(
            io.BytesIO(buffer.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{product_id}.csv"
        )
    elif filetype == "xlsx":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{product_id}.xlsx"
        )