import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://nkbdata_user:FnQsBhzhV6OH9L71A6ai2uhAAJYhWBIr@dpg-cv3f228gph6c738qcheg-a.oregon-postgres.render.com/nkbdata'
    SQLALCHEMY_TRACK_MODIFICATIONS = False