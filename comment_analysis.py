import json
import boto3
import os
import re

# import requests

region_name = 'eu-central-1'

comprehend = boto3.client(service_name='comprehend', region_name=region_name)
bedrock = boto3.client('bedrock-runtime', region_name=region_name)
sns = boto3.client('sns')
topic_arn = os.environ.get('SNS_TOPIC_ARN')
email_substring = "An email has been sent for this issue:"



def lambda_handler(event, context):
    print("Event data type : ",type(event))
    print("Event  ----   ",event)
    
    body = json.loads(event['body'])
    sentiment = None
    
    project_key = body['issue']['fields']['project']['key']
    issue_key = body['issue']['key']
    print("Issue key : ", issue_key )
    reporter_display_name = body['issue']['fields']['reporter']['displayName']
    if body['issue']['fields']['assignee'] is not None:
        assignee_display_name = body['issue']['fields']['assignee']['displayName']
    else:
        assignee_display_name = "Unassigned"

    comment_key= body['comment']['id']
    comment = body['comment']
    if body['issue']['fields']['attachment'] is not None:
        attachments = body['issue']['fields']['attachment']
        print("ATTACHMENT json  ", attachments)
        attachment_filename = body['issue']['fields']['attachment'][0]['filename']
        
        # Extract filenames
        filenames = [item['filename'] for item in body['issue']['fields']['attachment']]
        max_id_attachment = max(attachments, key=lambda x: x['id'])
        print("-------------------------",max_id_attachment['filename'])
        # Print the filenames
        for filename in filenames:
            print(filename)
    
        print("ATTACHMENT : ", attachment_filename)
    
    text = comment['body']
    print("THIS IS THE ACTUAL COMMENT",text)
    
    # Condition checks if the comment is email
    if text.find(email_substring) == 0:
        index_check = text.find(email_substring)
        print("substring index : ", index_check)
        index = text.find(issue_key)
        if index != -1:
            print("+++++++")
            modified_text = text[index + 1 + len(issue_key):]
            print("Cleaned comment :")
            # send modified_text to comprehend
            print(modified_text)
            if len(modified_text)>2:
                comprehend_response = comprehend.detect_sentiment(Text=modified_text, LanguageCode='en')
                final_comment = modified_text
                sentiment = comprehend_response['Sentiment']
        else:
            print("Issue key not found in text")

    # If issue_key exists in the text, remove everything before it
    start_index = text.find("!")
    end_index = text.rfind("!")

    if max_id_attachment['filename'] in text:
        print("Attachment found in comment.")
        
        # if start_index != -1 and end_index != -1:
        cleaned_comment = text[:start_index] + text[end_index+1:]
        print("length of cleaned comment", len(cleaned_comment))
        # send cleaned_comment to comprehend
        if len(cleaned_comment)>2:
                comprehend_response = comprehend.detect_sentiment(Text=cleaned_comment, LanguageCode='en')
                final_comment = cleaned_comment
                sentiment = comprehend_response['Sentiment']
    else:
        print("Attachment not found in comment.")
        comprehend_response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
        final_comment = text
        sentiment = comprehend_response['Sentiment']
    if sentiment is not None:
        message = f'{sentiment} Comment\n Project: {project_key}\n Issue : {issue_key} \n  Assignee : {assignee_display_name}\n Reporter : {reporter_display_name}\n Coment : {final_comment}\n '
        print("Sentiment:", sentiment)
        # if sentiment == 'NEGATIVE' or 'negative':
        if sentiment.upper() == 'NEGATIVE':
            print("Sending")
            print(sentiment)
            response = sns.publish(
            TopicArn=topic_arn,
            Message=message
            )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'received'})
        }