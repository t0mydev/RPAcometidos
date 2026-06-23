from flask import Flask, render_template

# Unificamos ambas rutas hacia la carpeta static
app = Flask(__name__, template_folder="vue", static_folder="vue")

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
