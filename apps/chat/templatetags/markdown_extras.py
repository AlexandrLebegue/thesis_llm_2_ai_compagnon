import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def markdown(text):
    """
    Convert markdown text to HTML.
    This is a simple markdown parser for basic formatting.
    """
    if not text:
        return ""
    
    # Convert text to string if it isn't already
    text = str(text)
    
    # Handle line breaks
    text = text.replace('\n', '<br>')
    
    # Handle headers
    text = re.sub(r'^# (.*$)', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*$)', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.*$)', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^#### (.*$)', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    
    # Handle bold text
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Handle italic text
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    
    # Handle inline code
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Handle code blocks
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    
    # Handle links
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Handle unordered lists
    text = re.sub(r'^- (.*$)', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text, flags=re.DOTALL)
    
    # Handle ordered lists
    text = re.sub(r'^\d+\. (.*$)', r'<li>\1</li>', text, flags=re.MULTILINE)
    
    # Handle blockquotes
    text = re.sub(r'^> (.*$)', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    
    return mark_safe(text)