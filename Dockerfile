# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

COPY bigdata-staging-vertexai-d12b90113f4b.json ./
RUN pwd


# Install production dependencies.
RUN pip install fastapi uvicorn gunicorn db-dtypes tabulate streamlit
RUN pip install aiohttp pandas numpy pickle-mixin tk-tools pyarrow workdays
RUN pip install google-cloud-storage google-cloud-bigquery oauth2 google-oauth2-tool gspread
RUN pip install google-cloud-aiplatform vertexai

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:$PORT"]
#CMD ["gunicorn", "-w", "3", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", ":8050", "--max-requests", "1000", "--max-requests-jitter", "100"]


#########
#CMD exec gunicorn main:app  --bind :$PORT --workers 1 -k uvicorn.workers.UvicornWorker
CMD ["streamlit", "run", "exchange_dealer.py", "--server.port=8080", "--server.address=0.0.0.0"]

