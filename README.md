# StackOverflow Scraper API
> **Overview**

This project involves creating a REST API using Python and Flask to replicate the functionality of specific endpoints from the StackExchange API specification. The API will scrape data from the StackOverflow website using BeautifulSoup and implement the required filters, parameters, and paging as outlined in the specification.

## Project Structure
> **stackoverflow_scraper.py:**

Contains the Flask application and the API implementation.

> **requirements.txt:** 

Lists all Python dependencies for the project.

## API Specification

> **Endpoints**
The API should implement the following:

- All 4 built-in filters described by the StackExchange API specification.
- Parameters: min, max, fromdate, todate, sort, and any other parameters available for each endpoint.
- Paging: Implement paging as described by the StackExchange API specification.

> **Exclusions**

The API does not need to:

- Return object fields that require authentication.
- Implement parameters not available for an endpoint (including min, max, fromdate, todate, sort).
- Include quota_max and quota_remaining fields.

> **URL Structure**

- Do not include an API version number in the endpoint paths.
- For example, if the documentation describes an endpoint as /foo, the path should be available directly after the root as /foo.

- please note that when selecting your port it will take you to a home page with the following:

{
"error": "404 Not Found: The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again."
}

Please note that this will change once the endpoint has been put in.

> **Error Handling**

- Return appropriate HTTP response error codes:
- 400 Bad Request for invalid resource requests or incorrect HTTP methods.

## Setup and Execution
- Clone the Repository:

## bash

- git clone <repository-url>
- cd <repository-directory>
- Create a Virtual Environment:

## bash

- python -m venv .venv
- source .venv/bin/activate
- Install Dependencies:

## bash

- pip install -r requirements.txt
- Run the Flask Application:

- Ensure the STACKOVERFLOW_API_PORT environment variable is set before running the application.

## bash

- export STACKOVERFLOW_API_PORT=<desired-port>
- python stackoverflow_scraper.py

