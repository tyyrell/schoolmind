from schoolmind import create_app
from schoolmind.db import init_database, seed_demo_data

app = create_app()
with app.app_context():
    init_database()
    seed_demo_data()
print("Seed complete.")
