import logging
import re
import time
import backoff
import requests
from requests.exceptions import RequestException
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
import requests
from typing import List, Dict, Union, Any, Optional
from datetime import datetime, timedelta, timezone
from dateutil.parser import *
from typing import Optional


app = Flask(__name__)

@backoff.on_exception(backoff.expo, RequestException)
def fetch_page(url: str, **kwargs) -> Optional[BeautifulSoup]:
    response = requests.get(url, **kwargs, verify = False)
    response.raise_for_status()  # Raises an HTTPError if the response was unsuccessful

    return BeautifulSoup(response.text, 'html.parser')

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
        soup = fetch_page(url)
        collectives = []

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
            url = f"{base_url}?tab=tags&page={page}&pagesize=30"
            soup = fetch_page(url)

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


#this was changed: Check and see if it works well or not: update: it works so refine!!!!!!!!!!!!!!!!!!!!

def get_external_links(url):
    external_links = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36'
        }
        soup = fetch_page(url, headers=headers)

        header = soup.find("div", class_="s-select")
        if header:
            external_div = header.find("optgroup", label="External links")
            if external_div:
                externals = external_div.find_all("option")
                external_website = ["website", "support", "twitter", "github", "facebook", "instagram"]

                for i, external in enumerate(externals):
                    if i >= len(external_website):
                        break

                    external_link = {
                        "type": external_website[i],
                        "link": external.get("data-url")
                    }

                    if external_link["link"]:
                        external_links.append(external_link)
                        print(external_link)

        if not external_links:
            print(f"No relevant external links found for {url}")

    except requests.RequestException as e:
        print(f"Error fetching external links for {url}: {str(e)}")

    return external_links


@app.route('/questions', methods=['GET'])
def get_questions():
    try:
        page = int(request.args.get('page', 1))
        pagesize = int(request.args.get('pagesize', 30))
        tags_param = request.args.get('tags', '')
        tags = tags_param.split(';')[:3]

        tags = [tag.strip() for tag in tags if tag.strip()]



        questions = get_detailed_questions(page, pagesize, tags)

        if not questions:
            return jsonify({"error": "No questions found or error occurred during scraping"}), 404

        return jsonify(questions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_detailed_questions(page: int = 1, pagesize: int = 30, tags: List[str] = None) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    try:
        if isinstance(tags, str):
            tag_list = tags.split(';')[:3]  # Split by semicolon and limit to 3 tags
        elif isinstance(tags, list):
            tag_list = tags[:3]  # Limit to 3 tags
        else:
            tag_list = []

        base_url = "https://stackoverflow.com/questions"

        if tag_list:
            tags_query = '+'.join(tag_list)  # Join tags with '+' for multi-tag queries
            url = f"{base_url}/tagged/{tags_query}?sort=RecentActivity&edited=true&page={page}&pagesize={pagesize}"
        else:
            url = f"{base_url}?tab=Active&page={page}&pagesize={pagesize}"

        soup = fetch_page(url, headers={'User-Agent': 'Mozilla/5.0'})
        question_summaries = soup.find_all("div", class_="s-post-summary")

        for summary in question_summaries:
            question: Dict[str, Any] = {}

            question_tags = [tag.text for tag in summary.find_all("a", class_="post-tag")]

            # Filter by specified tags
            if tag_list:
                if not all(tag.lower() in [t.lower() for t in question_tags] for tag in tag_list):
                    continue  # Skip this question if it doesn't match all specified tags

            question['tags'] = question_tags

            # Owner information
            owner_div = summary.find("div", class_="s-user-card")
            if owner_div:
                user_div = owner_div.find("div", class_="s-user-card--link d-flex gs4")
                user_link_div = user_div.find("a") if user_div else None
                user_link = user_link_div.get('href') if user_link_div else None
                user_id = user_link.split('/')[-2] if user_link else None

                user_type = soup.find("div", class_="s-badge")
                # normal registered user
                user_status = "registered"
                account_id = None

                if user_type:
                    if user_type.text == "Moderator":
                        user_status = "moderator"
                    elif user_type == "Unregistered":
                        user_status = "unregistered"

                if user_link:
                    url = f"https://stackoverflow.com{user_link}"
                    user_response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    if user_response.status_code == 200:
                        user_soup = BeautifulSoup(user_response.text, 'html.parser')
                        script_tags = user_soup.find_all("script")
                        for script in script_tags:
                            script_content = script.string
                            if script_content and "accountId" in script_content:
                                account_id_match = re.search(r'accountId:\s*(\d+)', script_content)
                                if account_id_match:
                                    account_id = account_id_match.group(1)
                                user_id_match = re.search(r'userId:\s*(\d+)', script_content)
                                if user_id_match:
                                    user_id = user_id_match.group(1)
                                break

                # Debug print for profile image
                img_element = owner_div.find("img", class_="s-avatar--image")

                reputation_span = owner_div.find("span", title="reputation score ")
                reputation = reputation_span.get_text(strip=True) if reputation_span else "0"

                question['owner'] = {
                    "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                    "user_type": user_status,
                    "profile_image": img_element['src'],
                    "display_name": user_link.split('/')[-1] if user_link else "Anonymous",
                    "link": f"https://stackoverflow.com{user_link}" if user_link else None,
                    "reputation": reputation

                }
                if account_id:
                    question['owner']["account_id"] = int(account_id)
                if user_id:
                    question['owner']["user_id"] = int(user_id)

            else:
                question['owner'] = {
                    "user_type": "does_not_exist",
                    "display_name": "User does not exist",
                    "link": None,
                    "reputation": "0"
                }

            # Question ID and link
            question_link = summary.find("h3", class_="s-post-summary--content-title").find("a")
            if question_link and question_link.has_attr('href'):
                question['question_id'] = int(question_link['href'].split('/')[2])
                question['link'] = f"https://stackoverflow.com{question_link['href']}"

                question['title'] = question_link.text


                # Fetch the timeline page for more accurate date information
                timeline_url = f"https://stackoverflow.com/posts/{question['question_id']}/timeline"
                timeline_response = requests.get(timeline_url, headers={'User-Agent': 'Mozilla/5.0'})
                timeline_soup = BeautifulSoup(timeline_response.text, 'html.parser')

                # Extract dates from the timeline
                timeline_entries = timeline_soup.find_all("tr", class_="event-rows")
                for entry in timeline_entries:
                    event_type = entry.get("data-eventtype")
                    date = entry.find("span", class_="relativetime")
                    if date and "title" in date.attrs:
                        date_str = date["title"]
                        if event_type == "question":
                            question['creation_date'] = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")
                        elif event_type == "closed":
                            question['closed_date'] = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")
                        elif event_type == "edit":
                            question['last_edit_date'] = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")
                        elif event_type == "locked":
                            question['locked_date'] = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")
                        elif event_type == "protected":
                            question['last_activity_date'] = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")


                # If dates are not found in timeline, try to extract from the question summary
                if 'creation_date' not in question:
                    date_span = summary.find('span', class_='relativetime')
                    question['creation_date'] = date_span["title"] if date_span and "title" in date_span.attrs else None

                if 'last_activity' not in question:
                    date_span = summary.find('span', class_='relativetime')
                    question['last_activity'] = date_span["title"] if date_span and "title" in date_span.attrs else None


                # Set default values for dates not found
                question.setdefault('closed_date', None)
                question.setdefault('last_edit_date', None)
                question.setdefault('last_activity', None)
                question.setdefault('locked', None)
                question.setdefault('protected', None)

            else:
                question['question_id'] = None
                question['link'] = None
                question['title'] = None
                question['creation_date'] = None
                question['closed_date'] = None
                question['last_edit_date'] = None
                question['last_activity_date'] = None



            # Content license extraction
            link = summary.find("a", class_=["js-share-link", "js-gps-track"])
            if link and "data-se-share-sheet-license-name" in link.attrs:
                question['content_license'] = link["data-se-share-sheet-license-name"]
            else:
                # Fallback to the previous method if this new approach doesn't work
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

            accepted_answer = summary.find("div", class_="s-post-summary--stats-item has-answers has-accepted-answer")
            has_accepted_answer = accepted_answer is not None

            # Determine if the question is answered based on the new logic
            if question['score'] > 0:
                question['is_answered'] = True
            elif question['score'] <= 0:
                question['is_answered'] = False
            else:
                question['is_answered'] = False


            if accepted_answer:
                question_link = summary.find("h3", class_="s-post-summary--content-title").find("a")
                if question_link and question_link.has_attr('href'):
                    question_url = f"https://stackoverflow.com{question_link['href']}"

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
                            break

                    if accepted_answer_div:
                        answer_id = accepted_answer_div.get('data-answerid') or accepted_answer_div.get(
                            'data-answer-id')
                        if answer_id:
                            question['accepted_answer_id'] = int(answer_id)
                        else:
                            print("Debug: No answer ID attribute found in accepted answer div")
                    else:
                        print(
                            f"Debug: No accepted answer div found using selectors. HTML Snippet:\n{question_soup.prettify()[:1000]}")
                else:
                    print("Debug: No question link found")
            else:
                print("No accepted answer indicator found in summary")

            questions.append(question)


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
def get_question_by_id(question_id: int) -> Optional[Dict[str, Any]]:
    try:
        url = f"https://stackoverflow.com/questions/{question_id}"
        soup = fetch_page(url, headers={'User-Agent': 'Mozilla/5.0'})

        question: Dict[str, Any] = {}

        # Question ID and link
        question['question_id'] = question_id
        question['link'] = url

        # Title
        title_element = soup.find("h1", class_="fs-headline1 ow-break-word mb8 flex--item fl1")
        question['title'] = title_element.text.strip() if title_element else None

        # Tags
        tags_container = soup.find("div", class_="d-flex ps-relative fw-wrap")
        question['tags'] = [tag.text for tag in
                            tags_container.find_all("a", class_="post-tag")] if tags_container else []

        # Owner information
        owner_div = soup.find("div", class_="post-layout--right")
        if owner_div:
            user_info = owner_div.find("div", class_="user-info")
            if user_info:
                user_link = user_info.find("a")
                user_id = user_link['href'].split('/')[-2] if user_link else None

                img_element = user_info.find("img")
                profile_image = img_element["src"] if img_element else None

                reputation_span = user_info.find("span", class_="reputation-score")
                reputation = reputation_span.text.strip() if reputation_span else "1"

                display_name = user_info.find("div", class_="user-details").find("a").text.strip()

                user_type = "registered"
                if "new-contributor-indicator" in str(user_info):
                    user_type = "new contributor"
                elif "mod-flair" in str(user_info):
                    user_type = "moderator"

                question['owner'] = {
                    "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                    "user_type": user_type,
                    "profile_image": profile_image,
                    "display_name": display_name,
                    "link": f"https://stackoverflow.com{user_link['href']}" if user_link else None,
                    "reputation": reputation
                }
            else:
                question['owner'] = {
                    "user_type": "does_not_exist",
                    "display_name": "User does not exist",
                    "link": None,
                    "reputation": "0"
                }
        else:
            question['owner'] = None

        # Dates
        creation_date = soup.find("time", itemprop="dateCreated")
        question['creation_date'] = creation_date['datetime'] if creation_date else None

        last_activity_date = soup.find("time", itemprop="dateModified")
        question['last_activity'] = last_activity_date['datetime'] if last_activity_date else None


        question['last_edit_date'] = None  # Set default value
        question['closed_date'] = None  # Set default value

        # Content license
        license_element = soup.find("div", class_="mt-auto d-flex jc-space-between fs-caption fc-black-400")
        if license_element:
            license_text = license_element.find("a", rel="license")
            question['content_license'] = license_text.text if license_text else "CC BY-SA 4.0"
        else:
            question['content_license'] = "CC BY-SA 4.0"  # Default if not found

        # Stats
        stats = soup.find("div", class_="js-vote-count")
        question['score'] = int(stats.text) if stats else 0

        answer_count = soup.find("h2", class_="mb0", text=lambda text: "Answers" in text if text else False)
        question['answer_count'] = int(answer_count.find_next("div").text) if answer_count else 0

        # View count
        view_count_div = soup.find("div", class_="d-flex fw-wrap pb8 mb16 bb bc-black-075")
        if view_count_div:
            view_count_text = view_count_div.find("div", class_="flex--item ws-nowrap mb8").text.strip()
            view_count_match = re.search(r'(\d+)', view_count_text)
            if view_count_match:
                question['view_count'] = int(view_count_match.group(1))
            else:
                question['view_count'] = 0
        else:
            question['view_count'] = 0

        # Is answered and accepted answer
        accepted_answer = soup.find("div", class_="answer accepted-answer")
        question['is_answered'] = accepted_answer is not None or question['answer_count'] > 0
        question['has_accepted_answer'] = accepted_answer is not None

        return question

    except requests.RequestException as e:
        print(f"Error fetching question {question_id}: {str(e)}")
        return None

# Usage in Flask route
@app.route('/questions/<int:question_id>', methods=['GET'])
def get_question_by_id_route(question_id):
    question = get_question_by_id(question_id)
    if question:
        return jsonify(question), 200
    else:
        return jsonify({"error": "Question not found"}), 404


@app.route('/answers/<int:answer_id>', methods=['GET'])
def get_answer_by_id(answer_id):
    try:
        answers = []
        # Correct URL to point to the specific answer using the answer_id
        url = f"https://stackoverflow.com/a/{answer_id}"
        soup = fetch_page(url, headers={'User-Agent': 'Mozilla/5.0'})

        answer_elements = soup.find_all("div", class_="answer")

        for answer_element in answer_elements:
            answer: Dict[str, Any] = {}

            # Answer ID
            answer['answer_id'] = answer_element.get('data-answerid')

            # Score
            score_element = answer_element.find("div", class_="js-vote-count")
            answer['score'] = int(score_element.text) if score_element else 0

            # Is accepted
            answer['is_accepted'] = 'accepted-answer' in answer_element.get('class', [])

            # Creation date
            creation_date = answer_element.find("time", itemprop="dateCreated")
            answer['creation_date'] = creation_date['datetime'] if creation_date else None

            # Last activity date
            last_activity_date = answer_element.find("time", itemprop="dateModified")
            answer['last_activity_date'] = last_activity_date['datetime'] if last_activity_date else None

            # Owner information
            owner_div = answer_element.find("div", class_="post-layout--right")
            if owner_div:
                user_info = owner_div.find("div", class_="user-info")
                if user_info:
                    user_link = user_info.find("a")
                    user_id = user_link['href'].split('/')[-2] if user_link else None

                    img_element = user_info.find("img")
                    profile_image = img_element["src"] if img_element else None

                    reputation_span = user_info.find("span", class_="reputation-score")
                    reputation = reputation_span.text.strip() if reputation_span else "1"

                    display_name = user_info.find("div", class_="user-details").find("a").text.strip()

                    user_type = "registered"
                    account_id = None
                    if "new-contributor-indicator" in str(user_info):
                        user_type = "new contributor"
                    elif "mod-flair" in str(user_info):
                        user_type = "moderator"

                    if user_link:
                        user_page_url = f"https://stackoverflow.com{user_link['href']}"
                        user_response = requests.get(user_page_url, headers={'User-Agent': 'Mozilla/5.0'})
                        if user_response.status_code == 200:
                            user_soup = BeautifulSoup(user_response.text, 'html.parser')
                            script_tags = user_soup.find_all("script")
                            for script in script_tags:
                                script_content = script.string
                                if script_content and "accountId" in script_content:
                                    account_id_match = re.search(r'accountId:\s*(\d+)', script_content)
                                    if account_id_match:
                                        account_id = account_id_match.group(1)
                                    user_id_match = re.search(r'userId:\s*(\d+)', script_content)
                                    if user_id_match:
                                        user_id = user_id_match.group(1)
                                    break

                        answer['owner'] = {
                            "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                            "user_type": user_type,
                            "account_id": account_id,
                            "profile_image": profile_image,
                            "display_name": display_name,
                            "link": f"https://stackoverflow.com{user_link['href']}" if user_link else None,
                            "reputation": reputation
                        }
                    else:
                        answer['owner'] = {
                            "user_type": "does_not_exist",
                            "display_name": "User does not exist",
                            "link": None,
                            "reputation": "0"
                        }
                else:
                    answer['owner'] = None

            answers.append(answer)

        return answers
    except requests.RequestException as e:
        return None

@app.route('/answers/<int:answer_id>', methods=['GET'])
def get_answer_by_id_route(answer_id):
    answer = get_answer_by_id(answer_id)
    if answer:
        return jsonify(answer), 200
    else:
        return jsonify({"error": "Answer not found"}), 404


@app.route('/questions/<int:question_id>/answers', methods=['GET'])
def get_answers_for_question(question_id):
    logging.debug(f"Function called with question_id: {question_id}")
    try:
        url = f"https://stackoverflow.com/questions/{question_id}"
        logging.debug(f"Requesting URL: {url}")
        soup = fetch_page(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:

            logging.debug("BeautifulSoup parsing completed")
        except Exception as e:
            logging.error(f"Error parsing HTML: {str(e)}", exc_info=True)
            return jsonify({"error": "Error parsing the page content"}), 500

        question_element = soup.find('div', id='question')
        if not question_element:
            logging.warning("Question not found")
            return jsonify({"error": "Question not found"}), 404

        question = {'question_id': question_id, 'answers': []}

        # Extract content license for the question
        license_element = question_element.find('div', class_='post-menu')
        if license_element:
            license_link = license_element.find('a', class_='js-license-link')
            if license_link:
                question['content_license'] = license_link.text.strip()

        try:
            answer_elements = soup.find_all("div", class_="answer")
            logging.debug(f"Found {len(answer_elements)} answer elements")
        except Exception as e:
            logging.error(f"Error finding answer elements: {str(e)}", exc_info=True)
            return jsonify({"error": "Error processing the page structure"}), 500

        for answer_element in answer_elements:
            try:
                answer: Dict[str, Any] = {}

                # Answer ID
                answer['answer_id'] = answer_element.get('data-answerid')

                # Score
                score_element = answer_element.find("div", class_="js-vote-count")
                answer['score'] = int(score_element.text) if score_element else 0

                # Is accepted
                answer['is_accepted'] = 'accepted-answer' in answer_element.get('class', [])

                # Creation date
                creation_date = answer_element.find("time", itemprop="dateCreated")
                answer['creation_date'] = creation_date['datetime'] if creation_date else None

                edit_date = answer_element.find('div', class_='grid--cell ws-nowrap mr16 mb8')
                answer['last_activity_date'] = edit_date['datetime'] if edit_date else None

                # Last activity date
                last_activity_element = answer_element.find('div', class_='grid--cell ws-nowrap mr16 mb8')
                if last_activity_element:
                    last_activity_time = last_activity_element.find('time')
                    if last_activity_time:
                        answer['last_activity_date'] = last_activity_time['datetime']

                # Owner information
                owner_div = answer_element.find("div", class_="post-layout--right")
                if owner_div:
                    user_info = owner_div.find("div", class_="user-info")
                    if user_info:
                        user_link = user_info.find("a")
                        user_id = user_link['href'].split('/')[-2] if user_link else None

                        img_element = user_info.find("img")
                        profile_image = img_element["src"] if img_element else None

                        reputation_span = user_info.find("span", class_="reputation-score")
                        reputation = reputation_span.text.strip() if reputation_span else "1"

                        display_name = user_info.find("div", class_="user-details").find("a")

                        user_type = "registered"
                        if "new-contributor-indicator" in str(user_info):
                            user_type = "new contributor"
                        elif "mod-flair" in str(user_info):
                            user_type = "moderator"

                        account_id = None
                        if user_link:
                            user_page_url = f"https://stackoverflow.com{user_link['href']}"
                            user_response = requests.get(user_page_url, headers={'User-Agent': 'Mozilla/5.0'})
                            if user_response.status_code == 200:
                                user_soup = BeautifulSoup(user_response.text, 'html.parser')
                                script_tags = user_soup.find_all("script")
                                for script in script_tags:
                                    script_content = script.string
                                    if script_content and "accountId" in script_content:
                                        account_id_match = re.search(r'accountId:\s*(\d+)', script_content)
                                        if account_id_match:
                                            account_id = account_id_match.group(1)
                                        user_id_match = re.search(r'userId:\s*(\d+)', script_content)
                                        if user_id_match:
                                            user_id = user_id_match.group(1)
                                        break

                        answer['owner'] = {
                            "user_id": int(user_id) if user_id and user_id.isdigit() else None,
                            "account_id": int(account_id) if account_id else None,
                            "user_type": user_type,
                            "profile_image": profile_image,
                            "display_name": display_name.text if display_name else None,
                            "link": f"https://stackoverflow.com{user_link['href']}" if user_link else None,
                            "reputation": reputation
                        }
                    else:
                        answer['owner'] = {
                            "user_type": "does_not_exist",
                            "display_name": "User does not exist",
                            "link": None,
                            "reputation": "0"
                        }
                else:
                    answer['owner'] = None

                question['answers'].append(answer)
            except Exception as e:
                logging.error(f"Error processing an answer: {str(e)}", exc_info=True)

        logging.debug("All answers processed successfully")
        return jsonify(question), 200

    except requests.RequestException as e:
        logging.error(f"Request error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error fetching answers: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

if __name__ == '__main__':
    import os

    port = int(os.getenv('STACKOVERFLOW_API_PORT', 23467))
    app.run(host='0.0.0.0', port=port)
