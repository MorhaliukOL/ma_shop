from datetime import datetime
from . import db


class OrderArchive(db.Model):
    __tablename__ = "order_archive"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    id_order = db.Column(db.Integer, db.ForeignKey('orders.id'))
    id_product = db.Column(db.Integer, db.ForeignKey('products.id'))
    price = db.Column(db.Numeric)
    date_archive = db.Column(db.DateTime, default=datetime.utcnow)

    def __str__(self):
        return f'<User {self.id}>'


class ProductCategories(db.Model):
    __tablename__ = "product_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000), unique=True)
    products = db.relationship("products")


class Cart(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('users.id'))
    id_product = db.Column(db.Integer, db.ForeignKey('products.id'))
    addition_date = db.Column(db.Date, default=datetime.today().date())
    user = db.relationship("users")
    product = db.relationship("products")


class News(db.Model):
    __tablename__= "news"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(1000))
    post = db.Column(db.Text)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    news_date = db.Column(db.Date, default=datetime.utcnow())


class Mark (db.Model):
    """
    Class to create table "marks" in database.
    Variables
    ----------
    id
    id_user
    id_product
    mark_date
    rating
    users_who_marked
    products_marked

    Methods
    -------
    __str__
    """
    __tablename__ = "marks"
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    id_product = db.Column(db.Integer, db.ForeignKey('products.id'))
    mark_date = db.Column(db.Date, default=datetime.today().date())
    rating = db.Column(db.Integer)
    users_who_marked = db.relationship("users")
    products_marked = db.relationship("product")

    def __str__(self):
        return f'<Mark id {self.id} is rating {self.rating} provided ' \
               f'for product {self.id_product} by user {self.id_user} on {self.mark_date}>'


class Comments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_product = db.Column(db.Integer, db.ForeignKey('products.id'))
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'))
    comment_date = db.Column(db.Date, default=datetime.today().date())
    body = db.Column(db.Text)


class Users(db.Model):
    """
    Class to create table "users" in database.
    Variables
    ----------
    id
    first_name
    second_name
    email
    password

    Methods
    -------
    __repr__
    __str__
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(500), nullable=False)
    second_name = db.Column(db.String(500))
    email = db.Column(db.String(500), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)

    def __repr__(self):
        return f"<User id: {self.id}>"

    def __str__(self):
        return f"<User id: {self.id}>"


class Products(db.Model):
    """
    Class to create products table in database.
    """
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500))
    price = db.Column(db.Numeric)
    image = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id'))
    deleted = db.Column(db.Boolean, default=False)
    added_to_cart = db.relationship("cart")
    ordered = db.relationship("order_products")
    marked = db.relationship("mark")

    def __str__(self):
        return f"<Id: {self.id}, name: {self.name}, price: {self.price}>"


class OrderProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_order = db.Column(db.Integer, db.ForeignKey('orders.id'))
    id_product = db.Column(db.Integer, db.ForeignKey('products.id'))


class Orders(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('users.id'))
    order_date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
