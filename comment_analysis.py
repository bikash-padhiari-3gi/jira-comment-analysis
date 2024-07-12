import json
import boto3
import os
import re
from botocore.exceptions import BotoCoreError, ClientError

# Initialize AWS clients
region_name = 'eu-central-1'
comprehend = boto3.client(service_name='comprehend', region_name=region_name)
sns = boto3.client('sns')
bedrock = boto3.client('bedrock-runtime', region_name="eu-central-1")
topic_arn = os.environ.get('SNS_TOPIC_ARN')

# Define substrings to identify email content
email_substring = "An email has been sent for this issue:"
email_reply_substring = "Reply above this line"

def lambda_handler(event, context):
        
    # print("Event data type:", type(event))
    print("Event:", event)
    
    # Parse the incoming event body
    body = json.loads(event['body'])
    project_key = body['issue']['fields']['project']['key']
    issue_key = body['issue']['key']
    reporter_display_name = body['issue']['fields']['reporter']['displayName']
    comment = body['comment']
    text = comment['body']
    
    # Log the received comment and text
    print('Comment:', comment)
    print(f"Initial text length: {len(text)}")
    
    # Step 1: Handle attachment and clean the comment body
    text = handle_attachment(body, text)
    print(f"Text length after attachment handling: {len(text)}")
    
    # Step 2: Check if the comment starts with email_substring and modify the text
    if text.startswith(email_substring):
        modified_text = text[text.find(issue_key) + len(issue_key) + 1:]
        print(f"Text length after email substring handling: {len(modified_text)}")
        text = modified_text
    
    # Step 3: Process the comment for email_reply_substring
    processed_text = process_comment(text, email_reply_substring)
    print(f"Text length after processing to remove email_substring and email_reply_substring comment: {len(processed_text)}")
    
    # Get the assignee's display name, if available
    if body['issue']['fields']['assignee'] is not None:
        assignee_display_name = body['issue']['fields']['assignee']['displayName']
    else:
        assignee_display_name = "Unassigned"
    
    # # Alternate Step 4 (Not much useful): This part removed all the data after the first occurence of theis pattern --{color: #XXXXXX}
    # pattern = r'\{color:#([A-Fa-f0-9]+)\}'

    # # Find the first match in the text
    # match = re.search(pattern, processed_text)
    
    # if match:
    #     # If a match is found, remove everything after (and including) the first match
    #     processed_text = processed_text[:match.start()]
    
    # Step 4: Process the comment to remove any colour formattings
    print(f"Text length before removing color tags from the comment: {len(processed_text)}")
    
    processed_text = remove_color_tags(processed_text)
    print(f"Text length after removing color tags from the comment: {len(processed_text)}")
    
    processed_text = remove_safelinks(processed_text)
    print(f"Text sent to LLM : {processed_text}")

    #Step 5: Further cleanup using LLM
    processed_text = bedrock_invoke(processed_text)
    print("**************************************************")
    print(f'Response from bedrock: {processed_text}')
    print("**************************************************")
    
    # Step 6: Analyze the sentiment of the processed comment
    sentiment = analyze_sentiment(processed_text)
    print("+++++++++++++++++++++++++++++++++")
    print(f"Text sent for sentiment analysis: {processed_text}")
    print("+++++++++++++++++++++++++++++++++")
    print("Sentiment:", sentiment)

    # Log project key, issue key, and reporter display name
    print(f"Project Key: {project_key}")
    print(f"Issue Key: {issue_key}")
    print(f"Reporter Display Name: {reporter_display_name}\n")
    
    
    # Step 7: If sentiment is detected, create and send a notification if negative
    if sentiment:
        message = create_message(sentiment, project_key, issue_key, assignee_display_name, reporter_display_name, processed_text)
        if sentiment.upper() == 'NEGATIVE':
            sent_status = send_notification(topic_arn, message)
            print(f"Message Sent: {sent_status}")

    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'received'})
    }

def handle_attachment(body, text):
    """
    Handles the removal of attachment references from the comment text.
    """
    attachments = body['issue']['fields'].get('attachment', [])
    if attachments:
        # Find the attachment with the maximum ID
        max_id_attachment = max(attachments, key=lambda x: x['id'])
        # Check if this attachment is mentioned in the text
        if max_id_attachment['filename'] in text:
            # Clean the text by removing references to the attachment
            cleaned_comment = clean_comment(text)
            return cleaned_comment
    return text

def analyze_sentiment(text):
    """
    Analyzes the sentiment of the given text using Amazon Comprehend.
    """
    if len(text) > 2:
        try:
            response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
            return response['Sentiment']
        except comprehend.exceptions.TextSizeLimitExceededException as e:
            print(f"Text size limit exceeded: {e}")
        except (BotoCoreError, ClientError) as e:
            print(f"Error during sentiment analysis: {e}")
    return None

def remove_safelinks(text):
    # Define the regex pattern to match the safelinks enclosed in <[ ... ]> tags
    pattern = r'<\[https://eur03\.safelinks\.protection\.outlook\.com/\?url=.*?\]>'
    
    # Use re.sub to remove all occurrences of the pattern
    result = re.sub(pattern, '', text)
    
    return result

def process_comment(text, search_string):
    """
    Processes the comment to remove content after the specified search string.
    """
    match = re.search(search_string, text)
    if match:
        return text[:match.end()].strip()
    return text

def clean_comment(text):
    """
    Cleans the comment by removing content between the first and last exclamation marks.
    """
    start_index = text.find("!")
    end_index = text.rfind("!")
    if start_index != -1 and end_index != -1:
        return text[:start_index] + text[end_index + 1:]
    return text

def create_message(sentiment, project_key, issue_key, assignee_display_name, reporter_display_name, comment):
    """
    Creates a message string with the sentiment analysis results and issue details.
    """
    return f'{sentiment} Comment\n Project: {project_key}\n Issue: {issue_key}\n Assignee: {assignee_display_name}\n Reporter: {reporter_display_name}\n Comment: {comment}\n'

def send_notification(topic_arn, message):
    """
    Sends a notification to the specified SNS topic.
    """
    try:
        sns.publish(
            TopicArn=topic_arn,
            Message=message
        )
        return True
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def remove_color_tags(input_string):
    # Define the regex pattern to match the color tags
    pattern = r'\{color[^}]*\}|\{color\}'
    
    # Initialize the result to the input string
    result = input_string
    
    # Use re.sub to remove all occurrences of the pattern in one go
    result = re.sub(pattern, '', result)
    
    return result

def bedrock_invoke (text):
    modelId = 'amazon.titan-text-express-v1'
    accept = 'application/json'
    content_type = 'application/json'
    body = json.dumps({
    "inputText":'As an expert in text analysis your task is to extract only the information from the provided string while removing sender name, recipient name, declaration or any signature data' + 'Strictly limit the response to extract the information from the email body data from the following email data enclosed within #' + f'#{text}#',
    "textGenerationConfig":
    {
        "maxTokenCount":512,
        "stopSequences":["User:"],
        "temperature":0,
        "topP":1
    }
    })
    # Sending prompt to the model
    response = bedrock.invoke_model(
        modelId = modelId,
        contentType = content_type,
        accept = accept,
        body = body
        )
    output=json.loads(response['body'].read().decode('utf-8'))
    output = output['results']
    output = output[0]['outputText']
    # output=json.dumps(response['body'])
    # result = output['results']['outputTest']
    return output
