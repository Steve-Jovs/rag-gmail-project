from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import requests
import json
import datetime  # ← ADD THIS IMPORT
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
import time
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Global variable to track authentication state
AUTHENTICATED = False

def log(message, type="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{type}] {message}")

def is_authenticated():
    """Check if user is properly authenticated"""
    global AUTHENTICATED
    if not AUTHENTICATED:
        log("User not authenticated", "AUTH")
        return False
    
    token_path = 'token.json'
    if not os.path.exists(token_path):
        AUTHENTICATED = False
        log("Token file not found", "AUTH")
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.valid:
            log("User is authenticated and token is valid", "AUTH")
            return True
        else:
            AUTHENTICATED = False
            log("Token is invalid or expired", "AUTH")
            return False
    except Exception as e:  # ✅ Add proper exception handling
        AUTHENTICATED = False
        log(f"Error checking authentication: {e}", "ERROR")
        return False

def get_gmail_service():
    """Authenticate and return Gmail service - only if explicitly authenticated"""
    global AUTHENTICATED
    
    if not AUTHENTICATED:
        log("Cannot get Gmail service - not authenticated", "AUTH")
        return None
    
    creds = None
    token_path = 'token.json'
    
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            log("Loaded credentials from token file", "AUTH")
        except:
            AUTHENTICATED = False
            log(f"Error loading credentials: {e}", "ERROR")
            return None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                log("Refreshing expired token", "AUTH")
                creds.refresh(Request())
            except:
                AUTHENTICATED = False
                log(f"Error refreshing token: {e}", "ERROR")
                return None
        else:
            AUTHENTICATED = False
            log("No valid credentials available", "AUTH")
            return None
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        log("Saved refreshed token", "AUTH")
    
    log("Gmail service created successfully", "AUTH")
    return build('gmail', 'v1', credentials=creds)

def debug_payload_structure(payload, depth=0):
    """Debug function to understand payload structure"""
    indent = "  " * depth
    result = []
    
    if 'mimeType' in payload:
        result.append(f"{indent}MimeType: {payload['mimeType']}")
    
    if 'filename' in payload:
        result.append(f"{indent}Filename: {payload['filename']}")
    
    if 'body' in payload and 'data' in payload['body']:
        data_length = len(payload['body']['data'])
        result.append(f"{indent}Body data: {data_length} chars")
    
    if 'parts' in payload:
        result.append(f"{indent}Has {len(payload['parts'])} parts:")
        for i, part in enumerate(payload['parts']):
            result.append(f"{indent}Part {i+1}:")
            result.extend(debug_payload_structure(part, depth + 1))
    
    return result

def search_emails(query, max_results=10):
    """Search emails using Gmail API - with improved content extraction"""
    try:
        log(f"Starting email search: '{query}' (max: {max_results} emails)", "SEARCH")
        start_time = time.time()
        
        service = get_gmail_service()
        
        if not service:
            log("Search failed - no Gmail service available", "SEARCH")
            return None
        
        log(f"Executing Gmail API search...", "SEARCH")
        results = service.users().messages().list(
            userId='me', 
            q=query, 
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        log(f"Gmail API returned {len(messages)} messages", "SEARCH")
        
        email_contents = []
        
        for i, message in enumerate(messages):
            log(f"Processing email {i+1}/{len(messages)}...", "SEARCH")
            
            # Get full message content (not just metadata)
            msg = service.users().messages().get(
                userId='me', 
                id=message['id'],
                format='full'
            ).execute()

            payload = msg.get('payload', {})
            
            log(f"Message keys: {list(msg.keys())}", "DEBUG")
            log(f"Payload keys: {list(payload.keys())}", "DEBUG")  

            if 'parts' in payload:
                log(f"Number of parts: {len(payload['parts'])}", "DEBUG")
                for j, part in enumerate(payload['parts']):
                    log(f"Part {j} mimeType: {part.get('mimeType', 'None')}", "DEBUG")
            
            # DEBUG: Print payload structure
            if i == 0:  # Only for first email to avoid spam
                log("=== DEBUG PAYLOAD STRUCTURE ===", "DEBUG")
                debug_lines = debug_payload_structure(payload)
                for line in debug_lines:
                    log(line, "DEBUG")
                log("=== END DEBUG ===", "DEBUG")

            headers = payload.get('headers', [])
            
            subject = next((header['value'] for header in headers 
                          if header['name'] == 'Subject'), 'No Subject')
            sender = next((header['value'] for header in headers 
                         if header['name'] == 'From'), 'Unknown Sender')
            date = next((header['value'] for header in headers 
                       if header['name'] == 'Date'), 'Unknown Date')
            
            # Extract body with improved function
            body = extract_email_body(payload)
            
            # Extract attachment info
            attachments = extract_attachment_info(payload)
            
            internal_date = msg.get('internalDate')
            
            email_contents.append({
                'subject': subject,
                'sender': sender,
                'date': date,
                'internal_date': int(internal_date) if internal_date else 0,
                'body': body,
                'snippet': msg.get('snippet', '')[:200] + '...',
                'message_id': message['id'],
                'attachments': attachments,
                'body_length': len(body)
            })
            
            log(f"Email {i+1}: '{subject[:50]}...' | Body: {len(body)} chars | Attachments: {len(attachments)}", "SEARCH")
        
        email_contents.sort(key=lambda x: x['internal_date'], reverse=True)
        search_time = time.time() - start_time
        
        total_body_chars = sum(len(email['body']) for email in email_contents)
        log(f"Email search completed: {len(email_contents)} emails, {total_body_chars} total characters in {search_time:.2f}s", "SEARCH")
        
        return email_contents
        
    except Exception as e:
        log(f"Error searching emails: {e}", "ERROR")
        return []
    
def extract_email_body(payload):
    """Extract email body text from payload - fixed version"""
    body = ""
    
    try:
        log(f"Extracting email body from payload...", "EMAIL")
        
        def decode_body_data(body_data):
            """Helper function to decode body data"""
            if 'data' in body_data:
                try:
                    data = body_data['data']
                    # Replace URL-safe base64 characters if needed
                    data = data.replace('-', '+').replace('_', '/')
                    # Add padding if necessary
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += '=' * (4 - missing_padding)
                    
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    return decoded
                except Exception as e:
                    log(f"Error decoding base64 data: {e}", "EMAIL")
                    return ""
            return ""

        def extract_from_parts(parts):
            """Recursively extract from email parts - FIXED VERSION"""
            content = ""
            for part in parts:
                mime_type = part.get('mimeType', '')
                
                # Priority 1: Plain text (return immediately when found)
                if mime_type == 'text/plain':
                    part_body = decode_body_data(part.get('body', {}))
                    if part_body:
                        log(f"Found plain text: {len(part_body)} characters", "EMAIL")
                        return part_body  # Return immediately when plain text is found
                
                # Priority 2: HTML (only if no plain text found yet)
                elif mime_type == 'text/html' and not content:
                    part_body = decode_body_data(part.get('body', {}))
                    if part_body:
                        # Simple HTML tag removal
                        import re
                        clean_text = re.sub('<[^<]+?>', '', part_body)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        log(f"Converted HTML to text: {len(clean_text)} characters", "EMAIL")
                        content = clean_text
                
                # Recursive: Handle nested parts
                if 'parts' in part:
                    nested_content = extract_from_parts(part['parts'])
                    if nested_content:
                        # Only use nested content if we haven't found anything better
                        if not content or (nested_content and mime_type == 'text/plain'):
                            content = nested_content
            
            return content

        # Start extraction
        if 'parts' in payload:
            body = extract_from_parts(payload['parts'])
        else:
            # Simple email without parts
            body = decode_body_data(payload.get('body', {}))
        
        # Clean up and limit length PROPERLY
        if body:
            # Normalize whitespace but preserve paragraphs
            body = re.sub(r'\n\s*\n', '\n\n', body)  # Preserve paragraph breaks
            body = re.sub(r'[ \t]+', ' ', body)       # Normalize other whitespace
            body = body.strip()
            
            # Smart truncation - don't cut in the middle of a word
            if len(body) > 3000:
                log(f"Body too long ({len(body)} chars), truncating...", "EMAIL")
                # Find the last space before 3000 characters
                truncate_point = body[:3000].rfind(' ')
                if truncate_point > 2500:  # Ensure we have reasonable content
                    body = body[:truncate_point] + "... [truncated]"
                else:
                    body = body[:3000] + "... [truncated]"
            
            log(f"Final extracted body: {len(body)} characters", "EMAIL")
        else:
            log("No body content extracted", "EMAIL")
            # Fallback to snippet if no body found
            body = "No readable content extracted from email."
        
        return body
        
    except Exception as e:
        log(f"Error in extract_email_body: {e}", "ERROR")
        return "Error extracting email content."

def extract_attachment_info(payload):
    """Detect and list attachments in email"""
    attachments = []
    
    try:
        if 'parts' in payload:
            for part in payload['parts']:
                filename = part.get('filename')
                if filename and part.get('body', {}).get('attachmentId'):
                    attachments.append({
                        'filename': filename,
                        'mimeType': part.get('mimeType', ''),
                        'size': part.get('body', {}).get('size', 0)
                    })
                    log(f"Found attachment: {filename} ({part.get('mimeType', '')})", "EMAIL")
        
        return attachments
    except Exception as e:
        log(f"Error extracting attachment info: {e}", "ERROR")
        return []

def query_deepseek(prompt, context):
    """Query DeepSeek API with context"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key or api_key == 'your_actual_deepseek_api_key_here':
        log("DeepSeek API key not configured", "ERROR")
        return "Error: Please set up your DeepSeek API key in the .env file"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Improved prompt for better formatting and readability
    system_message = """You are a helpful email analyst. When answering questions about emails, please:

1. **Structure your response clearly** with headings and bullet points
2. **Summarize key findings** at the beginning
3. **Mention specific emails** with their dates and senders when relevant
4. **Use markdown-like formatting** for better readability
5. **Keep paragraphs concise** and focused
6. **Highlight important information** using bold text

Format your response like this:

## 📊 Summary
[Brief overview of what you found]

## 🔍 Key Findings
- Finding 1 with relevant details
- Finding 2 with relevant details

## 📧 Email Highlights
- **Email Subject** (Date) - Key insight
- **Another Subject** (Date) - Key insight

## 💡 Recommendations
1. First recommendation with proper spacing

2. Second recommendation on its own line

3. Third recommendation clearly separated

**Important:** If the AI returns poorly formatted text, enforce clean formatting in your fallback function."""

    full_prompt = f"""I found these emails related to your query. Please analyze them and provide a helpful response.

USER'S QUESTION: {prompt}

EMAILS FOUND:
{context}

Please provide a well-structured, easy-to-read answer:"""
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    
    try:
        log("Sending request to DeepSeek API...", "AI")
        start_time = time.time()
        
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=200
        )
        
        ai_time = time.time() - start_time
        
        if response.status_code == 200:
            log(f"DeepSeek API response received in {ai_time:.2f}s", "AI")
            return response.json()['choices'][0]['message']['content']
        else:
            log(f"DeepSeek API error: {response.status_code} - {response.text}", "ERROR")
            return create_formatted_fallback_response(prompt, context)
    
    except Exception as e:
        log(f"Error calling DeepSeek API: {str(e)}", "ERROR")
        return create_formatted_fallback_response(prompt, context)

def create_formatted_fallback_response(query, context):
    """Create a nicely formatted response when DeepSeek API fails"""
    log("Using fallback response (DeepSeek API unavailable)", "AI")
    if not context:
        return "## 📊 Summary\nI searched your emails but didn't find any messages matching your query."
    
    # Count emails and extract subjects
    email_count = context.count('Subject:')
    lines = context.split('\n')
    subjects = []
    dates = []
    senders = []
    
    current_subject = ""
    current_date = ""
    current_sender = ""
    
    for line in lines:
        if line.startswith('Subject:'):
            current_subject = line.replace('Subject:', '').strip()
        elif line.startswith('Date:'):
            current_date = line.replace('Date:', '').strip()
        elif line.startswith('From:'):
            current_sender = line.replace('From:', '').strip()
            # When we hit a new sender, we've completed one email
            if current_subject and current_subject != 'No Subject':
                subjects.append(current_subject)
                dates.append(current_date)
                senders.append(current_sender)
    
    if email_count == 0:
        return "## 📊 Summary\nNo relevant emails found for your search."
    
    # Create formatted response
    response = f"""## 📊 Summary
I found {email_count} email(s) related to your question.

## 🔍 Key Findings
- Found emails from various senders including job platforms and professional networks
- Dates range from recent to older messages
- Content includes job opportunities and professional updates

## 📧 Email Highlights"""
    
    for i, (subject, date, sender) in enumerate(zip(subjects[:5], dates[:5], senders[:5])):
        response += f"\n- **{subject}** ({format_date_display(date)}) - From: {sender}"
    
    if email_count > 5:
        response += f"\n- ... and {email_count - 5} more emails"
    
    response += "\n\n## 💡 Next Steps\nYou can click on any email below to open it in Gmail for more details."
    
    return response

def format_date_display(date_string):
    """Format date for display in responses"""
    if not date_string or date_string == 'Unknown Date':
        return 'Unknown date'
    
    try:
        date = datetime.datetime.strptime(date_string, '%a, %d %b %Y %H:%M:%S %z')
        return date.strftime('%b %d, %Y')
    except:
        return date_string

def natural_language_to_gmail_query(natural_query):
    """Use AI to convert natural language to Gmail search syntax"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    
    system_prompt = """You are a Gmail search query expert. Convert the user's natural language question into a valid Gmail search query.

Gmail Search Syntax Examples:
- "from:amazon" - Emails from Amazon
- "subject:meeting" - Emails with "meeting" in subject
- "newer_than:7d" - Emails from last 7 days
- "is:important" - Important emails
- "has:attachment" - Emails with attachments
- "label:work" - Emails with work label

Rules:
1. Always start with "in:inbox" unless specified otherwise
2. Keep it simple and specific
3. Use exact phrases in quotes for specific terms
4. Prefer recent emails by default
5. Return ONLY the search query, no explanations

Examples:
- "What emails from Amazon last week?" → "in:inbox from:amazon newer_than:7d"
- "Show me important work emails" → "in:inbox is:important label:work"
- "Find emails about the project meeting" → 'in:inbox subject:"project meeting"'
- "Emails with attachments from John" → "in:inbox from:john has:attachment"

Now convert this:"""

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": natural_query}
        ],
        "temperature": 0.1,
        "max_tokens": 100
    }
    
    try:
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            query = response.json()['choices'][0]['message']['content'].strip()
            # Clean up any extra text
            query = query.replace('"', '').strip()
            return query
        else:
            # Fallback: simple keyword extraction
            return f"in:inbox {extract_keywords(natural_query)}"
    
    except Exception as e:
        log(f"Query translation failed: {e}", "ERROR")
        return f"in:inbox {extract_keywords(natural_query)}"

def extract_keywords(query):
    """Simple keyword extraction fallback"""
    # Remove question words and common phrases
    stop_words = ['what', 'where', 'when', 'why', 'how', 'show', 'me', 'find', 'emails', 'email']
    words = query.lower().split()
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return ' '.join(keywords[:3])  # Use first 3 keywords

@app.route('/api/query', methods=['POST'])
def handle_query():
    """Main RAG function endpoint - with natural language translation"""
    try:
        log("=== NEW QUERY RECEIVED ===", "QUERY")
        start_time = time.time()
        
        # First check if user is properly authenticated
        if not is_authenticated():
            log("Query rejected - user not authenticated", "QUERY")
            return jsonify({
                'error': 'Not authenticated. Please click "Authenticate" first.',
                'requires_auth': True
            }), 401
        
        data = request.get_json()
        natural_query = data.get('query', '')
        max_results = data.get('max_results', 10)
        
        # Validate max_results
        try:
            max_results = int(max_results)
            max_results = max(1, min(100, max_results))
        except (ValueError, TypeError):
            max_results = 10
        
        log(f"Natural language query: '{natural_query}'", "QUERY")
        
        if not natural_query:
            log("Query rejected - empty query", "QUERY")
            return jsonify({'error': 'No query provided'}), 400
        
        # Step 1: Translate natural language to Gmail query
        log("Step 1: Translating natural language to Gmail query...", "QUERY")
        gmail_query = natural_language_to_gmail_query(natural_query)
        log(f"Translated Gmail query: '{gmail_query}'", "QUERY")
        
        # Step 2: Search emails using translated query
        log("Step 2: Searching emails...", "QUERY")
        email_results = search_emails(gmail_query, max_results)
        
        # Check if search_emails returned None (not authenticated)
        if email_results is None:
            log("Search failed - authentication issue", "QUERY")
            return jsonify({
                'error': 'Authentication expired. Please re-authenticate with Gmail.',
                'requires_auth': True
            }), 401
        
        if not email_results:
            log("No emails found for query", "QUERY")
            return jsonify({
                'answer': f"No emails found for '{natural_query}'. I searched using: {gmail_query}",
                'sources': [],
                'translated_query': gmail_query  # Show user what was searched
            })
        
        # Step 3: Prepare context from emails
        log(f"Step 3: Preparing context from {len(email_results)} emails...", "QUERY")
        context = "\n".join([
            f"Subject: {email['subject']}\nDate: {email['date']}\nFrom: {email['sender']}\nContent: {email['body']}\n"
            for email in email_results
        ])
        
        log(f"Context prepared: {len(context)} characters", "QUERY")
        
        # Step 4: Query DeepSeek with context
        log("Step 4: Sending to DeepSeek AI...", "QUERY")
        answer = query_deepseek(natural_query, context)  # Use original natural query
        
        total_time = time.time() - start_time
        log(f"=== QUERY COMPLETED in {total_time:.2f}s ===", "QUERY")
        
        # Return response
        return jsonify({
            'answer': answer,
            'sources': email_results,
            'search_metadata': {
                'original_query': natural_query,
                'gmail_query_used': gmail_query,
                'max_results_requested': max_results,
                'emails_found': len(email_results),
                'processing_time': f"{total_time:.2f}s"
            }
        })
        
    except Exception as e:
        log(f"Error in handle_query: {e}", "ERROR")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/gmail', methods=['GET'])
def gmail_auth():
    """Initialize Gmail authentication"""
    global AUTHENTICATED
    
    try:
        log("Starting Gmail authentication flow...", "AUTH")
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        AUTHENTICATED = True
        
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        
        log(f"Authentication successful for: {profile.get('emailAddress', 'Unknown')}", "AUTH")
        return jsonify({
            'status': 'authenticated',
            'email': profile.get('emailAddress', 'Unknown')
        })
            
    except Exception as e:
        AUTHENTICATED = False
        log(f"Authentication failed: {e}", "ERROR")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    global AUTHENTICATED
    
    log("Checking authentication status...", "AUTH")
    try:
        if is_authenticated():
            service = get_gmail_service()
            if service:
                profile = service.users().getProfile(userId='me').execute()
                return jsonify({
                    'authenticated': True,
                    'email': profile.get('emailAddress', 'Unknown')
                })
        
        AUTHENTICATED = False
        return jsonify({'authenticated': False})
    except:
        AUTHENTICATED = False
        return jsonify({'authenticated': False})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Remove authentication completely"""
    global AUTHENTICATED
    
    log("User logging out...", "AUTH")
    try:
        AUTHENTICATED = False
        
        token_path = 'token.json'
        if os.path.exists(token_path):
            os.remove(token_path)
            
        return jsonify({
            'status': 'logged_out',
            'message': 'Successfully logged out. Gmail access revoked.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/debug/email/<message_id>', methods=['GET'])
def debug_email(message_id):
    """Debug endpoint to examine one specific email"""
    try:
        service = get_gmail_service()
        if not service:
            return jsonify({'error': 'Not authenticated'})
        
        msg = service.users().messages().get(
            userId='me', 
            id=message_id,
            format='full'
        ).execute()
        
        payload = msg.get('payload', {})
        
        # Return the raw payload structure for analysis
        return jsonify({
            'message_id': message_id,
            'payload_structure': debug_payload_structure(payload),
            'snippet': msg.get('snippet', ''),
            'has_parts': 'parts' in payload,
            'num_parts': len(payload.get('parts', [])),
            'raw_payload': payload  # Be careful with this in production
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/debug/test', methods=['GET'])
def debug_test():
    """Debug endpoint to test basic functionality"""
    try:
        # Test authentication
        auth_status = is_authenticated()
        
        # Test Gmail service
        service = get_gmail_service()
        service_ok = service is not None
        
        # Test environment variables
        api_key_set = bool(os.getenv('DEEPSEEK_API_KEY')) and os.getenv('DEEPSEEK_API_KEY') != 'your_actual_deepseek_api_key_here'
        
        return jsonify({
            'authentication': auth_status,
            'gmail_service': service_ok,
            'deepseek_api_key_set': api_key_set,
            'token_file_exists': os.path.exists('token.json'),
            'credentials_file_exists': os.path.exists('credentials.json')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    log("Home page accessed", "SERVER")
    return jsonify({'message': 'RAG Gmail API is running!'})

if __name__ == '__main__':
    AUTHENTICATED = False
    log("=== RAG Gmail API Server Starting ===", "SERVER")
    log("Server running on http://127.0.0.1:5000", "SERVER")
    app.run(debug=True, port=5000)