import json
import boto3
import os
# import requests

region_name = 'ap-south-1'

comprehend = boto3.client(service_name='comprehend', region_name=region_name)
sns = boto3.client('sns')
topic_arn = os.environ.get('SNS_TOPIC_ARN')
chunk=5000
# topic_arn = 'arn:aws:sns:ap-south-1:590183768298:jira-analysis-topic'

def lambda_handler(event, context):
    body = json.loads(event['body'])    
    project_key = body['issue']['fields']['project']['key']
    issue_key = body['issue']['key']
    reporter_display_name = body['issue']['fields']['reporter']['displayName']

    if body['issue']['fields']['assignee'] is not None:
        assignee_display_name = body['issue']['fields']['assignee']['displayName']
    else:
        assignee_display_name = "Unassigned"

    comment_key= body['comment']['id']
    comment = body['comment']    
    text = comment['body'] #this is what we need to send into coprehend
    text_size=len(text)
    
    if text_size <= 4000:
        # If text is smaller than or equal to 5000 bytes, use detect_sentiment
        response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
        sentiment = response['Sentiment']
        sentiment_scores = response['SentimentScore']
        print("Sentiment:", sentiment)
        
    else:
        # If text is larger than 5000 bytes, split it into smaller chunks and use batch_detect_sentiment
        text_chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        response = comprehend.batch_detect_sentiment(TextList=text_chunks, LanguageCode='en')
        
            
        # aggregating sentiment scores to then take average
        positive = 0
        negative = 0
        neutral = 0
        mixed = 0
        divider = 0
    
        for item in response['ResultList']:
            positive += item['SentimentScore']['Positive']
            negative += item['SentimentScore']['Negative']
            neutral += item['SentimentScore']['Neutral']
            mixed += item['SentimentScore']['Mixed']
            divider += 1
            
        positive /=  divider
        negative /= divider
        neutral /= divider
        mixed /= divider
        
        values = {'positive':positive, 'negative':negative, 'neutral':neutral, 'mixed':mixed}
        
        score = max(values.values())
        sentiment = max(values, key=values.get)
    
        print(score)
        print(f'Maximum sentiment is {sentiment} with a score of {score}')
    print("SENTIMENT : ", sentiment)    
    message = f'Negative Comment\n Project: {project_key}\n Issue : {issue_key} \n Comment : {text}\n Assignee : {assignee_display_name}\n Reporter : {reporter_display_name}\n '
    if sentiment == 'NEGATIVE' or 'negative':
        response = sns.publish(
        TopicArn=topic_arn,
        Message=message
        )
        
    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'received'})
    }

def detect_sentiment(text):
    response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
    return response['Sentiment']
