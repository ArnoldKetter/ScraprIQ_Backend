# Use an official Python runtime as a base image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your application will run on
EXPOSE 8000

# Command to run the application using Uvicorn
# Make sure 'main:app' matches your application file (main.py) and FastAPI app instance (app)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

  * `FROM python:3.10-slim-buster`: Specifies the base Python image. Using a `slim` version keeps the image size smaller.
  * `WORKDIR /app`: Sets the working directory inside the container.
  * `COPY . /app`: Copies all files from your current local directory (`ScraprIQ_Backend`) into the `/app` directory inside the container.
  * `RUN pip install -r requirements.txt`: Installs all dependencies listed in `requirements.txt`. `--no-cache-dir` saves space.
  * `EXPOSE 8000`: Informs Docker that the container listens on port 8000.
  * `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`: This is the command that runs your FastAPI application when the container starts. `--host 0.0.0.0` is essential for the app to be accessible from outside the container (like Render's network).