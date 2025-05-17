import re
import time

from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
import requests
from typing import List, Dict, Union, Any
from datetime import datetime, timedelta, timezone
from dateutil.parser import *

app = Flask(__name__)


# Error Handlers
@app.errorhandler(404)
def resource_not_found(e):
    return jsonify(error=str(e)), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error=str(e)), 405


@app.route('/collectives', methods=['GET'])
def get_collectives():
    try:
        url = "https://stackoverflow.com/collectives-all"
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        collectives = []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all collective divs
        collective_divs = soup.find_all("div", class_="flex--item s-card bs-sm mb12 py16 fc-black-500")

        for collective in collective_divs:
            # Extract the collective's name (title)
            name_elem = collective.find("a", class_="js-gps-track")
            name = name_elem.text.strip() if name_elem else "No name found"

            # Extract the link to the collective
            link = f"{name_elem['href']}" if name_elem and 'href' in name_elem.attrs else ""
            full_link = f"https://stackoverflow.com{link}"
            # Extract the description (if any)
            description_span = collective.find('span', class_="fs-body1 v-truncate2 ow-break-word")
            description = description_span.text.strip() if description_span else "No description found"

            # Extract the slug or type (if applicable)
            slug = name_elem['href'].split('/')[-1] if name_elem and 'href' in name_elem.attrs else "No slug found"

            tags = get_collective_tags(full_link)
            external_links = get_external_links(full_link)

            print(f"Collective: {name}")
            print(f"Number of tags: {len(tags)}")
            print(f"Number of external links: {len(external_links)}")

            collectives.append({
                "name": name,
                "link": link,
                "description": description,
                "slug": slug,
                "tags": tags,
                "external_links": external_links
            })

            # Add a small delay to avoid overwhelming the server
            time.sleep(1)

        return jsonify(collectives)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_collective_tags(base_url):
    tags = []
    page = 1
    while True:
        try:
            url = f"{base_url}?tab=tags&page={page}&pagesize=50"
            response = requests.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            tag_elements = soup.find_all("a", class_="s-tag post-tag")

            if not tag_elements:
                break

            for tag in tag_elements:
                tags.append(tag.text)

            page += 1
            time.sleep(1)  # Add a small delay between requests
        except requests.RequestException:
            break

    return tags


def get_external_links(url):
    external_links = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        print(f"Fetching links for: {url}")

        # List of URLs to exclude
        excluded_urls = [
            'https://www.facebook.com/officialstackoverflow/',
            'https://twitter.com/stackoverflow',
            'https://www.instagram.com/thestackoverflow'
        ]

        # Look for all links on the page
        links = soup.find_all('a')
        for link in links:
            href = link.get('href')
            if href:
                # Handle relative URLs
                if href.startswith('/'):
                    href = f"https://stackoverflow.com{href}"

                #NOT WORKING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                elif href.startswith('mailto:'):
                    href = f"mailto:awscollective@amazon.com{href}" or f"mailto:stackoverflow@twilio.com{href}"

                # Determine link type
                link_type = None
                if href.startswith('mailto:awscollective@amazon.com') and not href.startswith('/'):  #not working
                    # either!!!!!!!!!!!!!!!!!!!!!!!!!
                    link_type = 'support'
                elif href.endswith('contact?topic=15'):  # works
                    link_type = 'support'
                elif href.startswith('mailto:stackoverflow@twilio.com'):
                    link_type = 'support'
                elif 'twitter.com' in href:
                    link_type = 'twitter'
                elif 'github.com' in href:
                    link_type = 'github'
                elif 'facebook.com' in href:
                    link_type = 'facebook'
                elif 'instagram.com' in href:
                    link_type = 'instagram'
                elif href.startswith('https://aws.amazon.com'):
                    link_type = 'website'
                elif href.startswith('https://www.twilio.com/'):
                    link_type = 'website'

                # Exclude irrelevant internal Stack Overflow links and specific URLs
                if link_type and not any(href.startswith(excluded_url) for excluded_url in excluded_urls):
                    # Append only relevant external links
                    external_links.append({
                        "type": link_type,
                        "link": href
                    })

        if not external_links:
            print(f"No relevant external links found for {url}")

    except requests.RequestException as e:
        print(f"Error fetching external links for {url}: {str(e)}")

    return external_links


@app.route('/questions', methods=['GET'])
def get_questions():
    try:
        page = int(request.args.get('page', 1))
        pagesize = int(request.args.get('pagesize', 50))

        questions = get_detailed_questions(page, pagesize)

        if not questions:
            return jsonify({"error": "No questions found or error occurred during scraping"}), 404

        return jsonify(questions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_detailed_questions(page: int = 2, pagesize: int = 50) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    try:
        url = f"https://stackoverflow.com/questions?tab=Active&page={page}&pagesize={pagesize}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        question_summaries = soup.find_all("div", class_="s-post-summary")

        for summary in question_summaries:
            question: Dict[str, Any] = {}

            # Tags
            question['tags'] = [tag.text for tag in summary.find_all("a", class_="post-tag")]

            # Owner information
            owner_div = summary.find("div", class_="s-user-card")
            if owner_div:
                user_div = owner_div.find("div", class_="s-user-card--link d-flex gs4")
                user_link_div = user_div.find("a") if user_div else None
                user_link = user_link_div.get('href') if user_link_div else None
                user_id = user_link.split('/')[-2] if user_link else None

                # Debug print for profile image
                img_element = owner_div.find("img", class_="s-avatar--image")
                # if img_element:
                #     print(f"Debug: Found img element: {img_element}")
                #     print(f"Debug: img element attributes: {img_element.attrs}")
                # else:
                #     print("Debug: No img element found")

                question['owner'] = {
                    "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                    "user_type": "registered" if user_id else "unregistered",
                    "profile_image": img_element['src']
                    if owner_div.find("img", class_="s-avatar--image") else None,
                    "display_name": user_link.split('/')[-1] if user_link else "Anonymous",
                    "link": f"https://stackoverflow.com{user_link}" if user_link else None,
                    "reputation": owner_div.find("span", title="reputation score ").text

                }
                reputation_span = owner_div.find("span", title="reputation score ") if owner_div else None
                print(f"Debug: Reputation span: {reputation_span}")
                reputation = reputation_span.get_text(strip=True) if reputation_span else None
                print(f"Debug: Extracted reputation: {reputation}")
            else:
                question['owner'] = {
                    "user_type": "does_not_exist",
                    "display_name": "User does not exist",
                    "link": None
                }

            # Question ID and link
            question_link = summary.find("h3", class_="s-post-summary--content-title").find("a")
            if question_link and question_link.has_attr('href'):
                question['question_id'] = int(question_link['href'].split('/')[2])
                question['link'] = f"https://stackoverflow.com{question_link['href']}"
                question['title'] = question_link.text.strip()
            else:
                question['question_id'] = None
                question['link'] = None
                question['title'] = None

            # Date information
            date_link = owner_div.find('span', class_='relativetime') if owner_div else None
            date_link = date_link["title"]

            # access revisions page
            dates_page = requests.get("https://stackoverflow.com/post/" + str(id) + "/timeline")

            if dates_page.status_code == 200:
                dates_soup = BeautifulSoup(dates_page.content, "lxml")

                # get table revisions
                # table = dates_soup.find("table", class_="s-table")
                # table_entries = table.find_all("tr", attrs={"data-eventtype : history"})
                table = dates_soup.find("table", class_="s-table")
                if table:
                    table_entries = table.find_all("tr", attrs={"data-eventtype": "history"})

                last_edit_date = None
                locked_date = None
                protected_date = None
                last_activity = None

                for i in table_entries:
                    # get activity
                    activity = i.find("td", class_="wmn1").text
                    comment = i.find("td", class_="event-comment")
                    date = i.find("td", class_="date").text

                    # if "edited" in activity:
                    #     # TODO: check that the date is the most recent
                    #     # TODO: replace if the most recent
                    #     pass
                    #
                    # elif "locked" in activity:
                    #
                    #
                    #
                    # elif "protected" in activity:

                    if "edited" in activity:

                        last_edit_date = date

                    elif "locked" in activity:

                        locked_date = date

                    elif "protected" in activity:

                        protected_date = date

                    question['last_edit_date'] = last_edit_date

                    question['locked_date'] = locked_date

                    question['protected_date'] = protected_date

            elif dates_page.status_code == 400:

                print(f"Bad request for question ID: {question['question_id']}")

            else:

                print(f"Unexpected status code {dates_page.status_code} for question ID: {question['question_id']}")

        else:

            print("No question ID available to fetch timeline")


            last_activity = soup.find("a", href="?lastactivity")
            last_activity = last_activity["title"]

            question['creation_date'] = date_link
            print("past one")
            question['last_activity_date'] = last_activity
            print("past two")
            question['last_edit_date'] = last_activity
            print("past three")
            #question['closed_date'] = extract_date_from_summary(summary, ['.js-post-notice time',
            #                                                              'div.s-post-summary--meta time'])

            print("here")

            # Debug output
            print(f"Debug: Creation Date: {question.get('creation_date')}")
            print(f"Debug: Last Activity Date: {question.get('last_activity_date')}")
            print(f"Debug: Last Edit Date: {question.get('last_edit_date')}")
            print(f"Debug: Closed Date: {question.get('closed_date')}")
            print(f"Debug: Locked Date: {question.get('locked_date')}")
            print(f"Debug: Protected Date: {question.get('protected_date')}")

            # Content license extraction
            license_element = summary.find("div", class_="s-post-summary--meta")
            if license_element:
                license_text = license_element.find("div", class_="s-post-summary--meta-text")
                if license_text:
                    license_text = license_text.get_text(strip=True)
                    if "CC BY-SA 4.0" in license_text:
                        question['content_license'] = "CC BY-SA 4.0"
                    elif "CC BY-SA 3.0" in license_text:
                        question['content_license'] = "CC BY-SA 3.0"
                    else:
                        question['content_license'] = license_text
                else:
                    question['content_license'] = "CC BY-SA 4.0"  # Default if not found
            else:
                question['content_license'] = "CC BY-SA 4.0"  # Default if not found

            # Stats extraction
            stats_container = summary.find("div", class_="s-post-summary--stats")
            if stats_container:
                for item in stats_container.find_all("div", class_="s-post-summary--stats-item"):
                    title = item.get('title', '')
                    value_span = item.find("span", class_="s-post-summary--stats-item-number")
                    if value_span:
                        value = value_span.text.strip()
                        if "Score" in title:
                            question['score'] = int(value)
                        elif "answer" in title.lower():
                            question['answer_count'] = int(value)
                        elif "view" in title.lower():
                            if 'k' in value.lower():
                                question['view_count'] = int(float(value.lower().replace('k', '').strip()) * 1000)
                            else:
                                question['view_count'] = int(re.sub(r'\D', '', value))

                # If any stat is missing, set it to 0
                question['score'] = question.get('score', 0)
                question['answer_count'] = question.get('answer_count', 0)
                question['view_count'] = question.get('view_count', 0)
            else:
                print("Debug: Stats container not found")

            # Determine if the question has answers
            question['is_answered'] = bool(summary.find("div", class_="s-post-summary--stats-item has-answers"))

            # Check if there's an accepted answer indicated in the summary
            accepted_answer = summary.find("div", class_="s-post-summary--stats-item has-answers has-accepted-answer")

            if accepted_answer:
                question_link = summary.find("h3", class_="s-post-summary--content-title").find("a")
                if question_link and question_link.has_attr('href'):
                    question_url = f"https://stackoverflow.com{question_link['href']}"
                    print(f"Debug: Fetching question URL: {question_url}")

                    question_response = requests.get(question_url, headers={'User-Agent': 'Mozilla/5.0'})
                    question_response.raise_for_status()

                    question_soup = BeautifulSoup(question_response.text, 'html.parser')

                    # Try multiple selectors to find the accepted answer
                    selectors = [
                        "div.answer.accepted-answer",
                        "div[itemprop='acceptedAnswer']",
                        "div.accepted-answer",
                        "div.js-accepted-answer"
                    ]

                    accepted_answer_div = None
                    for selector in selectors:
                        accepted_answer_div = question_soup.select_one(selector)
                        if accepted_answer_div:
                            print(f"Debug: Found accepted answer using selector: {selector}")
                            break

                    if accepted_answer_div:
                        answer_id = accepted_answer_div.get('data-answerid') or accepted_answer_div.get(
                            'data-answer-id')
                        if answer_id:
                            question['accepted_answer_id'] = int(answer_id)
                            print(f"Debug: Accepted answer ID found: {answer_id}")
                        else:
                            print("Debug: No answer ID attribute found in accepted answer div")
                    else:
                        print(
                            f"Debug: No accepted answer div found using selectors. HTML Snippet:\n{question_soup.prettify()[:1000]}")
                else:
                    print("Debug: No question link found")
            else:
                print("Debug: No accepted answer indicator found in summary")

            # Optionally set these only if you want to keep the checks in the dictionary
            question['has_accepted_answer'] = 'accepted_answer_id' in question

            questions.append(question)

        print(f"Scraped page {page}")

    except requests.RequestException as e:
        print(f"Error fetching page {page}: {str(e)}")

    return questions


def handle_relative_time(time_str):
    now = datetime.now(timezone.utc)
    time_str = time_str.lower().strip()

    # Handle "today"
    if 'today' in time_str:
        return now

    # Handle "yesterday"
    elif 'yesterday' in time_str:
        return now - timedelta(days=1)

    # Handle "x days ago"
    match = re.match(r'(\d+) days? ago', time_str)
    if match:
        days_ago = int(match.group(1))
        return now - timedelta(days=days_ago)

    # Handle "x months ago" - approximating 30 days per month
    match = re.match(r'(\d+) months? ago', time_str)
    if match:
        months_ago = int(match.group(1))
        past_date = now - timedelta(days=months_ago * 30)
        return past_date

    # Handle "x years ago" - approximating 365 days per year
    match = re.match(r'(\d+) years? ago', time_str)
    if match:
        years_ago = int(match.group(1))
        past_date = now - timedelta(days=years_ago * 365)
        return past_date

    # Handle combinations like "x years, y months ago"
    match = re.match(r'(\d+) years?, (\d+) months? ago', time_str)
    if match:
        years_ago, months_ago = map(int, match.groups())
        past_date = now - timedelta(days=years_ago * 365 + months_ago * 30)
        return past_date

    # Handle "modified X secs ago"
    match = re.match(r'modified (\d+) secs? ago', time_str)
    if match:
        secs_ago = int(match.group(1))
        return now - timedelta(seconds=secs_ago)

    return None


def parse_date_from_text(date_text):
    try:
        date = parse(date_text)
        if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
            date = date.replace(tzinfo=timezone.utc)
        return date
    except ValueError:
        print(f"Debug: Failed to parse date from text: {date_text}")
        return None


def extract_date_from_summary(summary, selectors):
    for selector in selectors:
        date_elements = summary.select(selector)
        if date_elements:
            for date_element in date_elements:
                date_text = date_element.get_text(strip=True)
                date = handle_relative_time(date_text)
                if date:
                    return int(date.replace(tzinfo=timezone.utc).timestamp())
                date = parse_date_from_text(date_text)
                if date:
                    return int(date.replace(tzinfo=timezone.utc).timestamp())
    return None


def get_question_tags(base_url):
    tags = []
    page = 1
    while True:
        try:
            url = f"{base_url}?tab=tags&page={page}&pagesize=50"
            response = requests.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            tag_elements = soup.find_all("div", class_="s-post-summary--meta-tags d-inline-block tags js-tags")

            if not tag_elements:
                break

            for tag in tag_elements:
                tags.append(tag.text)

            page += 1
            time.sleep(1)  # Add a small delay between requests
        except requests.RequestException:
            break

    return tags


@app.route('/questions/<int:question_id>', methods=['GET'])
def get_question_by_id(question_id):
    url = f"https://stackoverflow.com/questions/{question_id}"
    response = requests.get(url)
    if response.status_code == 404:
        return resource_not_found('Question not found')

    soup = BeautifulSoup(response.text, 'html.parser')
    question_data = {
        'title': soup.select_one('.question-hyperlink').text,
        'body': soup.select_one('.post-text').text.strip(),
        'votes': soup.select_one('.vote-count-post').text,
        'tags': [tag.text for tag in soup.select('.post-tag')],
        'user': soup.select_one('.user-details a').text if soup.select_one('.user-details a') else 'Anonymous',
        'asked_date': soup.select_one('.relativetime').text,
    }

    return jsonify(question_data)


@app.route('/answers/<int:answer_id>', methods=['GET'])
def get_answer_by_id(answer_id):
    url = f"https://stackoverflow.com/a/{answer_id}"
    response = requests.get(url)
    if response.status_code == 404:
        return resource_not_found('Answer not found')

    soup = BeautifulSoup(response.text, 'html.parser')
    answer_data = {
        'body': soup.select_one('.post-text').text.strip(),
        'votes': soup.select_one('.vote-count-post').text,
        'user': soup.select_one('.user-details a').text if soup.select_one('.user-details a') else 'Anonymous',
        'answered_date': soup.select_one('.relativetime').text,
    }

    return jsonify(answer_data)


@app.route('/questions/<int:question_id>/answers', methods=['GET'])
def get_answers_for_question(question_id):
    url = f"https://stackoverflow.com/questions/{question_id}"
    response = requests.get(url)
    if response.status_code == 404:
        return resource_not_found('Question not found')

    soup = BeautifulSoup(response.text, 'html.parser')
    answers = []
    for answer in soup.select('.answer'):
        answer_data = {
            'body': answer.select_one('.post-text').text.strip(),
            'votes': answer.select_one('.vote-count-post').text,
            'user': answer.select_one('.user-details a').text if answer.select_one('.user-details a') else 'Anonymous',
            'answered_date': answer.select_one('.relativetime').text,
        }
        answers.append(answer_data)

    return jsonify(answers)


if __name__ == '__main__':
    import os

    port = int(os.getenv('STACKOVERFLOW_API_PORT', 23467))
    app.run(host='0.0.0.0', port=port)
