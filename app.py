import os
import uuid
import random
import json
import base64
import string
import streamlit as st
import boto3
import requests
from urllib.parse import urlparse
from openai import AzureOpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone
import re

# Load environment variables
load_dotenv()

client = AzureOpenAI(
    api_key=st.secrets["AZURE_OPENAI_API_KEY"],
    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"],
    api_version="2025-01-01-preview",
)

# ----------- AWS S3 config -------------
aws_access_key = st.secrets["AWS_ACCESS_KEY"]
aws_secret_key = st.secrets["AWS_SECRET_KEY"]
region_name = st.secrets["AWS_REGION"]
bucket_name = st.secrets["AWS_BUCKET"]
s3_prefix = st.secrets["S3_PREFIX"]
cdn_base_url = st.secrets["CDN_BASE"]
cdn_prefix_media = "https://media.suvichaar.org/"

s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=region_name,
)

# ----------- Helper: Canonical URL generator -------------
def generate_slug_and_urls(title):
    if not title or not isinstance(title, str):
        raise ValueError("Invalid title: Title must be a non-empty string.")

    slug = (
        title.lower()
        .replace(" ", "-")
        .replace("_", "-")
    )
    slug = ''.join(c for c in slug if c in string.ascii_lowercase + string.digits + '-')
    slug = slug.strip('-')

    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'
    nano_id = ''.join(random.choices(alphabet, k=10))
    nano = f"{nano_id}_G"
    slug_nano = f"{slug}_{nano}"

    canurl = f"https://suvichaar.org/stories/{slug_nano}"
    canurl1 = f"https://stories.suvichaar.org/{slug_nano}.html"

    return nano, slug_nano, canurl, canurl1

# ----------- Sidebar Chat -------------
with st.sidebar:
    st.header("Azure OpenAI Chat")
    user_question = st.text_input("Your question:")
    if st.button("Send"):
        if not user_question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Waiting for response..."):
                messages = [{"role": "user", "content": user_question}]
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.5,
                )
                st.success("Answer:")
                st.write(response.choices[0].message.content)

# ----------- Main Form -------------
st.title("Content Submission Form")
with st.form(key="content_form"):
    story_title = st.text_input("Story Title")
    meta_description = st.text_area("Meta Description")
    meta_keywords = st.text_input("Meta Keywords (comma separated)")
    content_type = st.selectbox("Select your contenttype", options=["News", "Article"])
    language = st.selectbox("Select your Language", options=["en-US", "hi-IN"])
    image_url = st.text_input("Image URL to upload to S3")
    html_file = st.file_uploader("Upload your Raw HTML File", type=["html", "htm"])
    categories = st.selectbox("Select your Categories",options=["Art","Travel","Entertainment","Literature","Books","Sports","History","Culture","Wildlife","Spiritual","Food"])
    submit_button = st.form_submit_button("Submit")

if submit_button:
    st.markdown("### Submitted Data")
    st.write(f"**Story Title:** {story_title}")
    st.write(f"**Meta Description:** {meta_description}")
    st.write(f"**Meta Keywords:** {meta_keywords}")
    st.write(f"**Content Type:** {content_type}")
    st.write(f"**Language:** {language}")

    key_path = "media/default.png"
    uploaded_url = None

    # Generate canonical info
    try:
        nano, slug_nano, canurl, canurl1 = generate_slug_and_urls(story_title)
        page_title = f"{story_title} | Suvichaar"
    except Exception as e:
        st.error(f"Error generating canonical URLs: {e}")
        nano = slug_nano = canurl = canurl1 = page_title = ""

    # ----------- Upload Image to S3 -------------
    if image_url:
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            filename = os.path.basename(urlparse(image_url).path)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".gif"]:
                ext = ".jpg"
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            s3_key = f"{s3_prefix}{unique_filename}"

            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=response.content,
                ContentType=response.headers.get("Content-Type", "image/jpeg"),
            )
            uploaded_url = f"{cdn_base_url}{s3_key}"
            key_path = s3_key
            st.success("Image uploaded successfully!")
            # st.image(uploaded_url, caption="Uploaded Image", use_container_width=True)

        except Exception as e:
            st.warning(f"Failed to fetch/upload image. Using fallback. Error: {e}")
    else:
        st.info("No Image URL provided. Using default.")

    # ----------- Modify HTML Template -------------
    try:
        template_path = r"C:\\Users\\DLPS\\OneDrive\\Desktop\\StoriesLab\\masterregex.html"
        with open(template_path, "r", encoding="utf-8") as file:
            html_template = file.read()

        html_template = html_template.replace("{{user}}", random.choice(["Onip", "Naman", "Mayank"]))
        html_template = html_template.replace("{{publishedtime}}", datetime.now(timezone.utc).isoformat(timespec='seconds'))
        html_template = html_template.replace("{{modifiedtime}}", datetime.now(timezone.utc).isoformat(timespec='seconds'))

        html_template = html_template.replace("{{storytitle}}", story_title)
        html_template = html_template.replace("{{metadescription}}", meta_description)
        html_template = html_template.replace("{{metakeywords}}", meta_keywords)
        html_template = html_template.replace("{{contenttype}}", content_type)
        html_template = html_template.replace("{{lang}}", language)

        html_template = html_template.replace("{{pagetitle}}", page_title)
        html_template = html_template.replace("{{canurl}}", canurl)
        html_template = html_template.replace("{{canurl1}}", canurl1)

        resize_presets = {
            "potraitcoverurl": (640, 853),
            "msthumbnailcoverurl": (300, 300),
            "image0": (720, 1200)
        }

        for label, (width, height) in resize_presets.items():
            template = {
                "bucket": "suvichaarapp",
                "key": key_path,
                "edits": {
                    "resize": {
                        "width": width,
                        "height": height,
                        "fit": "cover"
                    }
                }
            }
            encoded = base64.urlsafe_b64encode(json.dumps(template).encode()).decode()
            final_url = f"{cdn_prefix_media}{encoded}"
            html_template = html_template.replace(f"{{{{{label}}}}}", final_url)

        # ----------- Extract <style amp-custom> block from uploaded raw HTML -------------
        extracted_style = ""
        if html_file:
            raw_html = html_file.read().decode("utf-8")

            # Extract <style amp-custom> block
            style_match = re.search(r"(<style\s+amp-custom[^>]*>.*?</style>)", raw_html, re.DOTALL | re.IGNORECASE)
            if style_match:
                extracted_style = style_match.group(1)
            else:
                st.info("No <style amp-custom> block found in uploaded HTML.")

            # Extract <amp-story> block
            start = raw_html.find("<amp-story-page")
            end = raw_html.find("</amp-story>")
            extracted_amp_story = ""
            if start != -1 and end != -1:
                extracted_amp_story = raw_html[start:end + len("</amp-story>")]
            else:
                st.warning("No complete <amp-story> block found in uploaded HTML.")
        else:
            extracted_amp_story = ""

        # Insert extracted <style amp-custom> into <head> of your template before </head>
        if extracted_style:
            head_close_pos = html_template.lower().find("</head>")
            if head_close_pos != -1:
                html_template = (
                    html_template[:head_close_pos] +
                    "\n" + extracted_style + "\n" +
                    html_template[head_close_pos:]
                )
            else:
                st.warning("No </head> tag found in HTML template to insert <style amp-custom>.")

        # Insert extracted AMP story block inside template
        if extracted_amp_story:
            # Locate opening <amp-story> tag in template
            amp_story_opening_match = re.search(r"<amp-story\b[^>]*>", html_template)
            analytics_tag = '<amp-story-auto-analytics gtag-id="G-2D5GXVRK1E" class="i-amphtml-layout-container" i-amphtml-layout="container"></amp-story-auto-analytics>'

            if amp_story_opening_match and analytics_tag in html_template:
                insert_pos = amp_story_opening_match.end()
                # Insert the extracted story slides just after the opening tag, before analytics tag
                html_template = (
                    html_template[:insert_pos]
                    + "\n\n"
                    + extracted_amp_story
                    + "\n\n"
                    + html_template[insert_pos:]
                )
            else:
                st.warning("Could not find insertion points in the HTML template.")

        st.markdown("### Final Modified HTML")
        st.code(html_template, language="html")

        # Provide download button for final HTML
        st.download_button(
            label="Download Final HTML",
            data=html_template,
            file_name=f"{slug_nano}.html",
            mime="text/html",
        )

        # ----------- Generate and Provide Metadata JSON -------------
        metadata_dict = {
            "story_title": story_title,
            "categories": categories,
            "filterTags": "",
            "story_uid": nano,
            "story_link": canurl,
            "storyhtmlurl": canurl1,
            "urlslug": slug_nano,
            "cover_image_link": final_url,
            "publisher_id": "",
            "story_logo_link": "https://media.suvichaar.org/filters:resize/96x96/media/brandasset/suvichaariconblack.png",
            "keywords": meta_keywords,
            "metadescription": meta_description,
            "lang": language
        }

        json_str = json.dumps(metadata_dict, indent=4)
        st.download_button(
            label="Download Story Metadata (JSON)",
            data=json_str,
            file_name=f"{slug_nano}_metadata.json",
            mime="application/json",
        )

    except Exception as e:
        st.error(f"Error processing HTML: {e}")
