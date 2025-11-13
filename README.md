# Image Labeling Web App

A lightweight Flask-based web tool for annotating images.

## Features
- User authentication
- Load images and labels from Excel or JSON
- Interactive web interface for tagging
- Save results as JSON per image

## Run locally
```
pip install -r requirements.txt
python app.py
```

## Deploy to Render
- Connect your GitHub repo
- Add a new "Web Service"
- Select `Python 3` environment
- Set **Start Command** to:
  ```
  gunicorn app:app
  ```
