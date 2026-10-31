FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-ranking.txt ./
RUN pip install --no-cache-dir -r requirements-ranking.txt
COPY app.py .
COPY rank_dataset.py .
COPY rank_fei.py .
COPY rank_api.py .
COPY download_celebrities.py .
COPY prepare_asian.py .
COPY templates templates
ENV HOST=0.0.0.0 PORT=8080 GALLERY_DATA=/data
VOLUME /data
EXPOSE 8080
CMD ["python", "app.py"]
