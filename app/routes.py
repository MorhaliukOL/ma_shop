import psycopg2
import io
from flask import render_template, request, redirect, url_for, flash, g, session, send_file
from . import app

from .db_utils.config import DATABASE
from news import news_
from users import validation, user
from product_categories import product_categories, category_validation
from errors import errors
from comments import comments
from products import products
from marks import mark
from cart import cart


@app.before_request
def get_db():
    if not hasattr(g, 'db'):
        g.db = psycopg2.connect(**DATABASE)


@app.teardown_request
def close_db(error):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/image/<ln>')
def image(ln):
    sn = products.get_product_image(g.db, ln)
    return send_file(io.BytesIO(sn), mimetype='image/jpeg')



@app.route('/')
def index():
    return render_template("index.html")


@app.route('/catalogue')
def catalogue():
    return render_template("catalogue.html")


@app.route('/product/product_description/<product_id>', methods=("GET", "POST"))
def show_product(product_id):
    avg_mark = mark.get_average(g.db, product_id)
    with g.db.cursor() as cursor:
        cursor.execute(f"select id, name, price, image from products where id = '{product_id}'")
        prod_data = cursor.fetchone()
        comment = ""
        if request.method == "POST":
            comment = request.form.get("comment", "")
            if 'user_id' not in session:
                flash("Please log in for leaving your comment")
                return redirect(url_for('login'))
            else:
                comments.add(g.db, product_id, session['id_user'], comment)
        return render_template("product_description.html", data=prod_data, comment=comment, avg_mark=avg_mark)


@app.route('/cart', methods=("GET", "POST"))
def cart_call():
    cart_items = {}
    if "user_id" in session:
        if request.method == "POST":
            cart.delete(g.db, int(session["user_id"]), int(request.form.get("delete_item", "")))
        for product_id in cart.get_all(g.db, int(session["user_id"])):
            if product_id not in cart_items:
                name, price = products.get_for_cart(g.db, product_id)
                cart_items[product_id] = {
                    "product_id": product_id,
                    "name": name,
                    "price": price,
                    "pieces": 1
                }
            else:
                cart_items[product_id]["pieces"] += 1
    return render_template("cart.html", cart_items=cart_items)


@app.route('/news')
def news():
    all_news = news_.get_all(g.db)
    return render_template("news.html", news=all_news)


@app.route('/contacts')
def contacts():
    return render_template("contacts.html")


@app.route('/logout')
def logout():
    if "user_id" in session:
        session.pop("user_id")
        flash("You logged out")
        return redirect(url_for('index'))
    else:
        flash("You are not logged in")
        return redirect(url_for('index'))


@app.route('/login', methods=("GET", "POST"))
def login():
    message = email = ""
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if validation.login_form_validation(email, password):
            try:
                session['user_id'] = user.login(g.db, email, password)
                flash("You are logged")
                return redirect(url_for('index'))
            except errors.StoreError:
                message = "Wrong password or email"

        else:
            message = "Something wrong, check form"

    return render_template("login.html", message=message, email=email)


@app.route('/registration', methods=("GET", "POST"))
def registration():
    message = first_name = second_name = email = ""
    if request.method == "POST":
        first_name = request.form.get("first_name", "")
        second_name = request.form.get("second_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if validation.register_form_validation(first_name, second_name, email, password):
            try:
                user.add(g.db, first_name, second_name, email, password)
                flash("Registration was successful")
                return redirect(url_for('index'))
            except psycopg2.errors.UniqueViolation:
                message = f"User with email: {email} already exist"
        else:
            message = "Something wrong, check form"

    return render_template("registration.html", message=message, first_name=first_name,
                           second_name=second_name, email=email)


@app.route('/admin/add_category', methods=("GET", "POST"))
def add_category():
    category_name = message = ''
    if request.method == "POST":
        category_name = request.form.get("category_name", "")
        if category_validation.validator(category_name):
            try:
                product_categories.create(g.db, category_name)
                flash("Category added")
                return redirect(url_for('index_admin'))
            except errors.StoreError:
                message = f"Category with name: {category_name} already exist"
        else:
            message = "Something wrong, check form"

    return render_template("add_category.html", message=message, category_name=category_name)


@app.route('/admin')
def index_admin():
    return render_template("index_admin.html")


@app.route('/admin/add_product', methods=("GET", "POST"))
def add_product():
    message = ''
    all_categories = product_categories.get_all(g.db)
    if request.method == "POST":
        product_name = request.form.get("product_name", "")
        price = request.form.get("price", "")
        img = request.files['img'].read()
        category = request.form.get("category")
        try:
            products.add_product(g.db, product_name, price, img, category)
            message = 'Product added'
            redirect(url_for('add_product'))
        except errors.StoreError:
            message = "Smth wrong, pls check form"
    return render_template("add_product.html", all_categories=all_categories, message=message)


@app.route('/categories', methods=("GET", "POST"))
def categories():
    if request.method == "POST":
        if session["user_id"]:
            cart.add(g.db, session["user_id"], request.form.get("add_to_cart", ""))
    all_categories = product_categories.get_all(g.db)
    all_products = products.get_all(g.db)
    return render_template("categories.html", categories=all_categories, products=all_products)


@app.route('/admin/add_news', methods=("GET", "POST"))
def add_news():
    title, post = '', ''
    if request.method == "POST":
        title = request.form.get("title", "")
        post = request.form.get("post", "")
        id_user = session.get('user_id', 1)
        if not title or not post:
            flash('All fields must be filled in')
            redirect(url_for('add_news'))
        else:
            news_.add(g.db, title, post, id_user)
    return render_template('add_news.html', title=title, post=post)


@app.route('/admin/edit_category/', methods=("GET", "POST"))
def edit_category():
    new_name = category_id = ""
    all_categories = product_categories.get_all(g.db)
    if request.method == "POST":
        category_id = int(request.form.get("category", ""))
        new_name = request.form.get("new_name", "")
        if category_validation.validator(new_name):
            try:
                product_categories.update(g.db, category_id, new_name)
                flash("Category updated")
                return redirect(url_for('index_admin'))
            except psycopg2.errors.UniqueViolation:
                flash(f"Category {new_name} already exist")
            except errors.StoreError:
                flash("Something wrong, check form")
        else:
            flash("Something wrong, check form")
    return render_template("edit_category.html", all_categories=all_categories, new_name=new_name, category_id=category_id)


@app.route('/admin/delete_category', methods=("GET", "POST"))
def delete_category_list():
    all_categories = product_categories.get_all(g.db)
    return render_template("delete_category.html", all_categories=all_categories)


@app.route('/admin/delete_category/<string:category_id>', methods=("GET", "POST"))
def delete_category(category_id):
    try:
        product_categories.delete(g.db, category_id)
    except psycopg2.DatabaseError:
        flash("smths wrong")
        redirect(url_for(index_admin))
    return redirect(url_for('delete_category_list'))


@app.route('/admin/list_products', methods=("GET", "POST"))
def list_products():
    all_products = products.get_all_2(g.db)
    return render_template("list_products.html", all_products=all_products)


@app.route('/admin/edit_product/<string:product_id>', methods=("GET", "POST"))
def edit_product(product_id):
    product = products.get_product_2(g.db, product_id)
    categories = product_categories.get_all(g.db)
    print(categories)
    if request.method == "POST":
        id = request.form.get("product_id", "")
        name = request.form.get("product_name", "")
        price = request.form.get("price", "")
        img = request.files['img'].read()
        category = request.form.get("category", "")
        try:
            products.edit_product_2(g.db, id, name, price, category, img)
            flash("Product edited")
            return redirect(url_for('list_products'))
        except errors.StoreError:
            flash("Smth wrong, pls try again")
    return render_template("edit_product.html", product=product, categories=categories)


@app.route('/admin/change_news', methods=("GET", "POST"))
def change_news():
    all_news = news_.get_all(g.db)
    return render_template("change_news.html", news=all_news)


@app.route('/admin/delete_news/<string:news_id>', methods=("GET", "POST"))
def delete_news(news_id):
    news_.delete(g.db, news_id)
    return redirect(url_for('change_news'))


@app.route('/admin/edit_news/<string:news_id>', methods=("GET", "POST"))
def edit_news(news_id):
    if request.method == "POST":
        new_title = request.form.get("title", "")
        new_post = request.form.get("post", "")
        news_.edit_news(g.db, news_id, new_title, new_post)
        return redirect(url_for("change_news"))


@app.route("/admin/delete_product", methods=("GET", "POST"))
def delete_product():
    all_products = products.get_all(g.db)
    return render_template("delete_product.html", products=all_products)


@app.route("/admin/delete_confirm/<product_id>", methods=("GET", "POST"))
def delete_confirm(product_id):
    product_ = products.get_product(g.db, product_id)
    return render_template("delete_confirm.html", id=product_id, product=product_)


@app.route("/admin/delete_confirm/delete/<product_id>", methods=("GET", "POST"))
def delete(product_id):
    products.delete_product(g.db, product_id)
    flash("Deleted")
    return redirect("/admin/delete_product")


@app.route('/product/set_mark/<string:product_id>', methods=("GET", "POST"))
def set_product_mark(product_id):
    if request.method == "POST":
        product_mark = request.form.get("mark", "")
        if 'user_id' not in session:
            flash("Please log in for leaving your mark")
            return redirect(url_for('login'))
        else:
            if int(product_mark) <= 0 or int(product_mark) > 5:
                flash("Mark should be between 1 and 5")
            else:
                mark.add(g.db, session['id_user'], product_id, product_mark)
                flash("Your mark has been added successfully")
        return redirect(url_for('product'))


"""@app.route('/cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = products.get_product(product_id)
    cart_item = CartItem(product=product)
    db.session.add(cart_item)
    db.session.commit()
    return render_tempate('home.html', product=products)"""