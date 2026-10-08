# Despliegue en Streamlit Community Cloud

1. Cree un repositorio en GitHub (por ejemplo `peru_sein_dashboard`) y suba estos archivos.
   - Incluya `data/geo/` (snapshot OSM) y `data/reference/`. `data/raw/` queda fuera (ver `.gitignore`).
2. Entre a https://share.streamlit.io y elija **New app**.
3. Repositorio: `TU_USUARIO/peru_sein_dashboard` · Rama: `main` · Archivo principal: `app.py`.
4. Python 3.11+ recomendado. Las dependencias se instalan desde `requirements.txt`.
5. Publique. La URL tendrá la forma `https://<nombre>.streamlit.app`.

## Prueba local antes de publicar
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Actualizar datos
Edite los CSV y haga *commit*; la app se recarga automáticamente al desplegar.
