import io
from pathlib import Path
from datetime import datetime
from PIL import Image
from flask import render_template, request, redirect, url_for, flash, g, session, send_file, abort
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from app.config import basedir, ITEMS_PER_PAGE, STATUS_ORDER
from . import validation
from .forms import AddProductForm, CommentsForm, CategoryForm, MarkForm, NewsForm, RestorePasswordForm, \
    SetNewPasswordForm, UpdateOrderForm, UserLoginForm, UserRegistrationForm, ContactUsForm
from .models import OrderArchive, ProductCategories, Cart, News, Mark, Comments, Users, Products, OrderProduct, Orders, \
    Messages, app, check_password_hash, db
from .login import login_required, admin_role_required
from .api import order_archive_schema, orders_archive_schema, order_product_schema, order_products_schema, order_schema, \
    orders_schema, cart_schema, carts_schema, comment_schema, comments_schema, product_category_schema, \
    product_categories_schema, product_schema, products_schema, user_schema, users_schema
from .send_mail import send_mail
from .registration_token import generate_confirmation_token, confirm_token


def save_image_and_thumbnail(image_data, product_id):
    """save image and image_thumbnail"""
    image = Image.open(image_data)
    rgb_im = image.convert('RGB')
    image_name = f"{product_id}.jpg"
    rgb_im.save(Path(basedir, app.config['UPLOAD_FOLDER'], image_name))
    rgb_im.thumbnail(app.config['THUMBNAIL_SIZE'])
    thumbnail_name = f"{product_id}_thumbnail.jpg"
    rgb_im.save(Path(basedir, app.config['UPLOAD_FOLDER'], thumbnail_name))


@app.teardown_request
def close_db(error):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    return render_template("index.html")


def paging(items, page_template):
    next_url = url_for(page_template, page=items.next_num) \
        if items.has_next else None
    prev_url = url_for(page_template, page=items.prev_num) \
        if items.has_prev else None
    return next_url, prev_url


@app.route('/product/product_description/<product_id>', methods=("GET", "POST"))
def show_product(product_id):
    form = MarkForm()
    form_c = CommentsForm()
    raw_avg = db.session.query(func.avg(Mark.rating)).filter(Mark.id_product == product_id).first()
    avg_mark = round(raw_avg[0], 2) if raw_avg[0] is not None else 'No marks yet'
    number_of_marks = db.session.query(func.count(Mark.rating)).filter(Mark.id_product == product_id).first()[0]
    product = Products.query.filter_by(id=product_id).first()
    product_category = ProductCategories.query.get(product.category_id).name
    comments_list = db.session.query(Comments).join(Users).\
        add_columns(Users.first_name, Comments.comment_date, Comments.comment_body).\
        filter(Comments.id_product==product_id).all()
    return render_template("product_description.html", product=product, #comments_list=comments_list,
                           avg_mark=avg_mark, form=form, number_of_marks=number_of_marks,
                           product_category=product_category, form_c=form_c)


@app.route('/product/add_comment/<string:product_id>', methods=("GET", "POST"))
@login_required
def add_comment(product_id):
    form_c = CommentsForm()
    new_comment = form_c.comment_body.data
    comment_body = Comments(session['user_id'], product_id, new_comment)
    db.session.add(comment_body)
    db.session.commit()
    flash("Your comment has been added successfully")
    return redirect(f'/product/product_description/{product_id}')


@app.route('/product/set_mark/<string:product_id>', methods=("GET", "POST"))
@login_required
def set_product_mark(product_id):
    form = MarkForm()
    new_mark = form.mark.data
    if Mark.query.filter_by(id_user=session['user_id'], id_product=product_id).first() is not None:
        db.session.query(Mark).filter(Mark.id_user == session['user_id'], Mark.id_product == product_id). \
            update({Mark.rating: new_mark})
        db.session.commit()
        flash("Your mark has been updated successfully")
    else:
        mark = Mark(session['user_id'], product_id, new_mark)
        db.session.add(mark)
        db.session.commit()
        flash("Your mark has been added successfully")
    return redirect(f'/product/product_description/{product_id}')


@app.route('/product/add_to_cart/<product_id>', methods=("GET", "POST"))
@login_required
def add_to_cart(product_id):
    if request.method == "POST":
        to_cart = Cart(id_user=session["user_id"], id_product=product_id)
        db.session.add(to_cart)
        db.session.commit()
    return redirect(url_for("get_catalogue"))


@app.route('/cart', methods=("GET", "POST"))
@login_required
def cart_call():
    cart_items = {}
    items_qty = 0
    total_amount = 0
    if request.method == "POST":
        Cart.query.filter_by(id_user=session["user_id"], id_product=request.form.get("delete_item", "")).delete()
        db.session.commit()
    products = db.session.query(Cart.id_product, Products.name, Products.price) \
        .filter(Products.id == Cart.id_product, Cart.id_user == session["user_id"], Products.deleted == 'False').all()
    for product in products:
        if product[0] not in cart_items:
            name, price = product[1], product[2]
            cart_items[product[0]] = {
                "product_id": product[0],
                "name": name,
                "price": price,
                "pieces": 1
            }
            cart_items[product[0]]["amount"] = cart_items[product[0]]["price"] * cart_items[product[0]]["pieces"]
        else:
            cart_items[product[0]]["pieces"] += 1
            cart_items[product[0]]["amount"] += cart_items[product[0]]["price"]
        total_amount += cart_items[product[0]]["price"]
        items_qty += 1
    return render_template("cart.html", cart_items=cart_items, items_qty=items_qty, total_amount=total_amount)


@app.route('/news')
def news():
    page = request.args.get('page', 1, type=int)
    news = db.session.query(News) \
        .join(Users) \
        .add_columns(News.title, News.post, News.news_date, Users.first_name, Users.second_name) \
        .filter(Users.id == News.id_user).paginate(page, ITEMS_PER_PAGE, False)
    next_url, prev_url = paging(news, 'news')
    return render_template("news.html", news=news.items, next_url=next_url, prev_url=prev_url)


@app.route('/contacts', methods=("GET", "POST"))
def messaging():
    form = ContactUsForm()
    if request.method == "POST":
        new_message = form.message.data
        sender = form.sender.data
        e_mail = form.e_mail.data
        message = Messages(sender, e_mail, new_message)
        db.session.add(message)
        db.session.commit()
        return redirect(url_for("message_sent"))
    return render_template("contacts.html", form=form)


@app.route('/contacts/message_sent')
def message_sent():
    return render_template("message_sent.html")


@app.route('/logout')
@login_required
def logout():
    session.pop("user_id")
    if "next_page" in session:
        session.pop("next_page")
    flash("You have logged out")
    return redirect(url_for('index'))


@app.route('/login', methods=("GET", "POST"))
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    message = ""
    form = UserLoginForm()
    if request.method == "POST":
        email = form.email.data
        password = form.password.data
        try:
            user = Users.query.filter_by(email=email).first()
            if check_password_hash(user.password, password):
                session['user_id'] = user.id
                if 'next_page' in session:
                    return redirect(session["next_page"])
                flash("You are logged in")
                return redirect(url_for("index"))
            else:
                message = "Wrong email or password"
        except AttributeError:
            message = "Wrong email or password"
    return render_template("login.html", form=form, message=message)


@app.route('/registration', methods=("GET", "POST"))
def registration():
    if 'user_id' in session:
        return redirect(url_for('index'))
    message = ""
    form = UserRegistrationForm()
    if request.method == "POST":
        first_name = form.first_name.data
        second_name = form.second_name.data
        email = form.email.data
        password = form.password.data
        if validation.register_form_validation(first_name, second_name, password):
            try:
                if email == "admin@example.com":
                    user = Users(first_name, second_name, email, password, admin_role=True, confirmed=True)
                else:
                    user = Users(first_name, second_name, email, password, admin_role=False, confirmed=False)
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                flash(f"User with email {email} already exists")
            token = generate_confirmation_token(email)
            confirm_url = app.config['SITE_URL'] + url_for('confirmation', token=token)
            subject = "Please confirm your email"
            try:
                send_mail(email, subject, confirm_url)
            except ConnectionRefusedError as error:
                flash(f'Error sending email: {error}')
            flash('A confirmation email has been sent via email.')
            return redirect(url_for('index'))
        else:
            message = "Something went wrong, please check the form"

    return render_template("registration.html", message=message, form=form)


@app.route('/confirm/<token>')
def confirmation(token):
    email = confirm_token(token)
    if not email:
        flash('The confirmation link is invalid or has expired.')
        return redirect(url_for('index'))
    user = Users.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        flash('Account is already confirmed. Please log in.')
    else:
        user.confirmed = True
        db.session.add(user)
        db.session.commit()
        flash('You have confirmed your account. Thanks!')
    return redirect(url_for('login'))


@app.route('/admin/add_category', methods=("GET", "POST"))
@login_required
@admin_role_required
def add_category():
    """Admin: add category"""
    form = CategoryForm()
    if request.method == "POST" and form.validate():
        category = ProductCategories(name=form.name.data)
        db.session.add(category)
        db.session.commit()
        flash("Category added")
        return redirect(url_for('categories_list'))
    return render_template("add_category.html", form=form)


@app.route('/admin')
@login_required
@admin_role_required
def index_admin():
    return render_template("index_admin.html")


@app.route('/admin/add_product', methods=("GET", "POST"))
@login_required
@admin_role_required
def add_product():
    """function for add product in database"""
    form = AddProductForm()
    form.category_id.choices = [(int(category.id), category.name) for category in ProductCategories.query.all()]
    if request.method == "POST" and form.validate():
        product = Products(name=form.name.data,
                           price=form.price.data,
                           description=form.description.data,
                           category_id=form.category_id.data)
        db.session.add(product)
        db.session.commit()
        save_image_and_thumbnail(form.image.data, product.id)
        flash("Product added")
        return redirect(url_for('products_list'))
    return render_template("add_product.html", form=form)


@app.route('/catalogue/<category>', methods=("GET", "POST"))
@app.route('/catalogue', methods=("GET", "POST"))
def get_catalogue(category="all"):
    categories = ProductCategories.query.all()
    existing_categories = [str(category.id) for category in categories]
    if category not in existing_categories and category != "all":
        abort(404)
    page = request.args.get('page', 1, type=int)
    products = Products.query.filter_by(deleted=False).paginate(page, ITEMS_PER_PAGE, False)
    if category != "all":
        products = Products.query.filter_by(category_id=category, deleted=False).paginate(page, ITEMS_PER_PAGE, False)
    next_url, prev_url = paging(products, 'get_catalogue')
    return render_template("catalogue.html", categories=categories,
                           products=products.items, next_url=next_url, prev_url=prev_url)


@app.route('/admin/add_news', methods=("GET", "POST"))
@login_required
@admin_role_required
def add_news():
    form = NewsForm()
    if request.method == 'POST':
        try:
            new_news = News(title=form.title.data, post=form.post.data, id_user=session['user_id'])
            db.session.add(new_news)
            db.session.commit()
            flash('News was successfully added to db.')
        except IntegrityError:
            flash('News wasn\'t added to db.')
        return redirect(url_for('news'))

    return render_template('add_news.html', form=form)


@app.route('/admin/edit_category/<string:category_id>', methods=("GET", "POST"))
@login_required
@admin_role_required
def edit_category(category_id):
    category = ProductCategories.query.filter_by(id=category_id).first()
    form = CategoryForm()
    if request.method == "POST":
        try:
            form.populate_obj(category)
            db.session.commit()
            flash("Category updated")
        except IntegrityError:
            flash('Category was not edited!!')
        return redirect(url_for('categories_list'))
    elif request.method == "GET":
        form = CategoryForm(formdata=request.form, obj=category)
    return render_template("edit_category.html", form=form, category=category)


@app.route("/admin/confirm_delete_category/<category_id>", methods=("GET", "POST"))
@login_required
@admin_role_required
def confirm_delete_category(category_id):
    category_ = ProductCategories.query.filter_by(id=category_id).first()
    return render_template("confirm_delete_category.html", category=category_)


@app.route("/admin/confirm_delete_category/delete/<category_id>", methods=("GET", "POST"))
@login_required
@admin_role_required
def delete_category(category_id):
    ProductCategories.query.filter_by(id=category_id).delete()
    db.session.commit()
    flash("Deleted")
    return redirect(url_for('categories_list'))


@app.route('/admin/products_list', methods=("GET", "POST"))
@login_required
@admin_role_required
def products_list():
    page = request.args.get('page', 1, type=int)
    products = Products.query.filter_by(deleted=False).order_by(Products.id).paginate(page, ITEMS_PER_PAGE, False)
    categories = db.session.query(ProductCategories)
    next_url, prev_url = paging(products, 'products_list')
    return render_template("products_list.html", products=products.items,
                           categories=categories, next_url=next_url, prev_url=prev_url)


@app.route('/admin/edit_product/<string:product_id>', methods=("GET", "POST"))
@login_required
@admin_role_required
def edit_product(product_id):
    product = Products.query.filter_by(id=product_id).first()
    form = AddProductForm()
    form.category_id.choices = [(int(category.id), category.name) for category in ProductCategories.query.all()]
    if request.method == "POST" and form.validate():
        try:
            form.populate_obj(product)
            db.session.commit()
            flash("Product edited")
            if form.image.data:
                remove_images(f'{product_id}.jpg', f'{product_id}_thumbnail.jpg')
                save_image_and_thumbnail(form.image.data, product.id)
        except IntegrityError:
            flash('Product was not edited!!')
        return redirect(url_for('products_list'))
    elif request.method == "GET":
        form = AddProductForm(formdata=request.form, obj=product)
        form.category_id.choices = [(int(category.id), category.name) for category in ProductCategories.query.all()]
        form.category_id.default = (product.category_id, product.category.name)
    return render_template("edit_product.html", form=form, product_id=product.id)


@app.route('/admin/delete_news/<string:news_id>', methods=("GET", "POST"))
@login_required
@admin_role_required
def delete_news_id(news_id):
    News.query.filter(News.id == news_id).delete()
    db.session.commit()
    flash('News was successfully deleted from db.')
    return redirect(url_for('news_list'))


@app.route('/admin/news_list', methods=("GET", "POST"))
@login_required
@admin_role_required
def news_list():
    news = db.session.query(News) \
        .join(Users) \
        .add_columns(News.id, News.title, News.post, News.news_date,
                     Users.first_name, Users.second_name) \
        .filter(Users.id == News.id_user).all()
    return render_template("news_list.html", news=news)


@app.route('/admin/edit_news/<string:news_id>', methods=("GET", "POST"))
@login_required
@admin_role_required
def edit_news_id(news_id):
    post = News.query.filter(News.id == news_id).first()
    if request.method == 'POST':
        form = NewsForm(formdata=request.form, obj=post)
        form.populate_obj(post)
        db.session.commit()
        flash('News was successfully updated in db.')
        return redirect(url_for('news_list'))
    form = NewsForm(obj=post)
    return render_template('edit_news_id.html', post=post, form=form)


@app.route("/admin/delete_confirm/<product_id>", methods=("GET", "POST"))
@login_required
@admin_role_required
def delete_confirm(product_id):
    product = db.session.query(Products).filter_by(id=product_id).first()
    return render_template("delete_confirm.html", product=product)


@app.route("/admin/delete_confirm/delete/<product_id>", methods=("GET", "POST"))
@login_required
@admin_role_required
def delete(product_id):
    product = Products.query.filter_by(id=product_id, deleted=False).first()
    product.deleted = True
    db.session.commit()
    return redirect(url_for('products_list'))


def remove_images(*names):
    """Delete image"""
    for name in names:
        img_to_rem = Path(f"app/static/img/{name}")
        if img_to_rem.is_file():
            img_to_rem.unlink()
    return True


@app.route('/admin/categories_list', methods=("GET", "POST"))
@login_required
@admin_role_required
def categories_list():
    page = request.args.get('page', 1, type=int)
    categories = ProductCategories.query.order_by(ProductCategories.id).paginate(page, ITEMS_PER_PAGE, False)
    next_url, prev_url = paging(categories, 'categories_list')
    return render_template("categories_list.html", categories=categories.items,
                           next_url=next_url, prev_url=prev_url)


@app.context_processor
def inject_email():
    user_email = ''
    if 'user_id' in session:
        user = Users.query.filter_by(id=session['user_id']).first()
        user_email = user.email
    return {'user_email': user_email}


@app.route('/cart/create_order', methods=("GET", "POST"))
@login_required
def create_order():
    new_order = []
    if request.method == "POST":
        all_ids = db.session.query(Cart.id_product).filter(Cart.id_user == session['user_id']).all()
        all_ids = [i[0] for i in all_ids]
        user_order = Orders(id_user=session['user_id'], order_date=datetime.now())
        db.session.add(user_order)
        db.session.commit()
        try:
            send_mail(user_order.users.email, "Ma shop", f"Order #{user_order.id} was created")
        except ConnectionRefusedError as error:
            flash('Something wrong!')
        for product_id in all_ids:
            product_order = OrderProduct(id_order=user_order.id, id_product=product_id)
            db.session.add(product_order)
        Cart.query.filter_by(id_user=session["user_id"]).delete()
        db.session.commit()
    return render_template("create_order.html", new_order=new_order)


@app.route('/admin/manage_orders', methods=("GET", "POST"))
@login_required
@admin_role_required
def manage_orders():
    all_orders = db.session.query(Orders.id, Orders.id_user, Orders.order_date, Orders.status, OrderProduct.id_product) \
        .outerjoin(OrderProduct, Orders.id == OrderProduct.id_order)
    return render_template("manage_orders.html", all_orders=all_orders)


@app.route('/admin/update_order/<string:order_id>', methods=['GET', 'POST'])
@login_required
@admin_role_required
def update_order(order_id):
    order_user = Orders.query.filter_by(id=order_id).first()
    order_product = OrderProduct.query.filter_by(id_order=order_id).first()
    order_products = OrderProduct.query.filter_by(id_order=order_id).all()
    form = UpdateOrderForm()
    form.id_user.choices = [(int(user.id), user.get_full_name()) for user in Users.query.all()]
    form.id_product.choices = [(int(product.id), product.name) for product
                               in Products.query.filter_by(deleted="False").all()]
    form.status.choices = STATUS_ORDER
    if request.method == "POST" and form.validate():
        try:
            form.populate_obj(order_user)
            form.populate_obj(order_product)
            db.session.commit()
            if form.status.data == 'Completed':
                try:
                    create_archive_order(order_user, session["user_id"], order_id, order_products)
                    Orders.query.filter_by(id=order_id).delete()
                    db.session.commit()
                except IntegrityError:
                    flash("Order is not archived!")
            flash("Order edited")
        except IntegrityError:
            flash('Order was not edited!!')
        return redirect(url_for('manage_orders'))
    return render_template("update_order.html", form=form)


def create_archive_order(order, order_user, order_id, order_products):
    order_json = order_schema.dump(order)
    products_json = products_schema.dump(order_products)
    archive_order = OrderArchive(id_user=order_user, id_order=order_id,
                                 order_information=order_json, order_product=products_json)
    db.session.add(archive_order)
    db.session.commit()


@app.route("/set_new_password/<token>", methods=("GET", "POST"))
def set_new_password(token):
    form = SetNewPasswordForm()
    email = confirm_token(token)
    if request.method == "POST":
        new_password = form.password.data
        if email:
            if validation.password_validator(new_password):
                password_hash = generate_password_hash(new_password)
                db.session.query(Users).filter(Users.email == email).update({Users.password: password_hash})
                db.session.commit()
                flash("Your password successfully updated")
                return redirect(url_for("login"))
            else:
                flash("Invalid password")
        else:
            flash("You used invalid link, try again")
    return render_template('set_new_password.html', form=form)


@app.route('/password_recovery', methods=("GET", "POST"))
def password_recovery():
    form = RestorePasswordForm()
    if request.method == "POST":
        email = form.email.data
        user_exists = bool(Users.query.filter_by(email=email).first())
        token = generate_confirmation_token(email)
        reset_url = app.config["SITE_URL"] + url_for("set_new_password", token=token)
        subject = "Follow this link to reset you password"
        if user_exists:
            try:
                send_mail(email, subject, reset_url)
                flash('Email with link to restore your password has been sent to you via email.', 'success')
            except ConnectionRefusedError:
                flash("Cannot connect to the server to send you an email")
        else:
            flash(f"There is no user with email '{email}'")
    return render_template("password_recovery.html", form=form)
