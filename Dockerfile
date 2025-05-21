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