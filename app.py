from flask import Flask, render_template, request, jsonify, url_for
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import json
import base64

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch', methods=['POST'])
def fetch_url():
    data = request.json
    url = data.get('url')
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # 使用更完整的请求头，模拟正常浏览器行为
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # 检查是否需要处理重定向或cookie问题
        if response.history:
            print(f"请求被重定向: {response.history}")
        
        # 处理可能的状态码
        if response.status_code == 403:
            # 尝试使用不同的User-Agent重试一次
            headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'
            response = session.get(url, headers=headers, timeout=15)
        
        # Check if the request was successful
        if response.status_code == 200:
            # 尝试确定正确的编码
            if response.encoding.lower() == 'iso-8859-1':
                # 尝试从内容中检测编码
                content_type = response.headers.get('Content-Type', '')
                if 'charset=' in content_type:
                    charset = content_type.split('charset=')[-1].split(';')[0].strip()
                    response.encoding = charset
                else:
                    # 尝试自动检测
                    response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Base URL for resolving relative links
            base_url = url
            
            # Process links to make them go through our proxy
            for link in soup.find_all(['a', 'link']):
                if link.has_attr('href'):
                    href = link['href']
                    # Skip javascript, anchors, and other non-navigable links
                    if href.startswith('javascript:') or href.startswith('#'):
                        continue
                    
                    # Handle relative URLs
                    if not href.startswith(('http://', 'https://')):
                        # Handle relative paths
                        if href.startswith('/'):
                            # Absolute path from domain root
                            parsed_url = urllib.parse.urlparse(base_url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        else:
                            # Relative path from current location
                            href = urllib.parse.urljoin(base_url, href)
                    
                    # Encode URL to pass through our proxy
                    encoded_url = base64.urlsafe_b64encode(href.encode()).decode()
                    link['href'] = f"javascript:loadUrl('{encoded_url}')"
                    link['target'] = '_self'  # Ensure links open in the same window
            
            # Process forms to submit through our proxy
            for form in soup.find_all('form'):
                if form.has_attr('action'):
                    action = form['action']
                    if not action.startswith(('http://', 'https://')):
                        action = urllib.parse.urljoin(base_url, action)
                    
                    # Add a hidden input with the original action
                    hidden_input = soup.new_tag('input')
                    hidden_input['type'] = 'hidden'
                    hidden_input['name'] = '_proxy_original_action'
                    hidden_input['value'] = action
                    form.append(hidden_input)
                    
                    # Change the form to submit to our proxy
                    form['action'] = '/submit_form'
                    form['method'] = 'POST'
                    
                    # Add onsubmit handler to intercept form submission
                    form['onsubmit'] = "return interceptFormSubmit(this);"
            
            # Remove script and style elements that might contain text not meant for reading
            for script in soup(["script", "noscript", "svg"]):
                script.extract()
            
            # Get page title
            title = soup.title.string if soup.title else "Untitled Page"
            
            # Find text blocks
            blocks = []
            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'article', 'div', 'section']):
                if element.name in ['div', 'section'] and not element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5']):
                    continue
                
                text = element.get_text().strip()
                if len(text) > 50:  # Only consider substantial blocks of text
                    blocks.append({
                        'id': f'block-{len(blocks)}',
                        'text': text,
                        'tag': element.name,
                        'length': len(text)
                    })
            
            # Sort blocks by length to identify the main content
            blocks.sort(key=lambda x: x['length'], reverse=True)
            
            # Try to determine the main content block
            main_content_id = blocks[0]['id'] if blocks else None
            
            return jsonify({
                'status': 'success',
                'title': title,
                'url': url,
                'blocks': blocks,
                'main_content_id': main_content_id,
                'html': str(soup),
                'original_url': url
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to fetch the URL. Status code: {response.status_code}'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        })

@app.route('/submit_form', methods=['POST'])
def submit_form():
    form_data = request.form
    original_action = form_data.get('_proxy_original_action')
    
    if not original_action:
        return jsonify({'status': 'error', 'message': 'No original form action provided'})
    
    # Create a new form data without our custom fields
    filtered_form_data = {k: v for k, v in form_data.items() if k != '_proxy_original_action'}
    
    try:
        # Submit the form to the original action URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': urllib.parse.urlparse(original_action).netloc,
            'Referer': original_action
        }
        
        session = requests.Session()
        response = session.post(original_action, data=filtered_form_data, headers=headers, timeout=15, allow_redirects=True)
        
        # 处理可能的状态码
        if response.status_code == 403:
            # 尝试使用不同的User-Agent重试一次
            headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'
            response = session.post(original_action, data=filtered_form_data, headers=headers, timeout=15)
        
        # Return the response similar to the fetch_url function
        if response.status_code == 200:
            # 尝试确定正确的编码
            if response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding
                
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Process the response similar to fetch_url
            # (we can extract this common functionality to a helper function in a production app)
            
            # Get page title
            title = soup.title.string if soup.title else "Untitled Page"
            
            # Find text blocks
            blocks = []
            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'article', 'div', 'section']):
                if element.name in ['div', 'section'] and not element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5']):
                    continue
                
                text = element.get_text().strip()
                if len(text) > 50:  # Only consider substantial blocks of text
                    blocks.append({
                        'id': f'block-{len(blocks)}',
                        'text': text,
                        'tag': element.name,
                        'length': len(text)
                    })
            
            # Sort blocks by length to identify the main content
            blocks.sort(key=lambda x: x['length'], reverse=True)
            
            # Try to determine the main content block
            main_content_id = blocks[0]['id'] if blocks else None
            
            return jsonify({
                'status': 'success',
                'title': title,
                'url': original_action,
                'blocks': blocks,
                'main_content_id': main_content_id,
                'html': str(soup),
                'original_url': original_action
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Form submission failed. Status code: {response.status_code}'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'An error occurred during form submission: {str(e)}'
        })

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')
    engine = data.get('engine', 'bing')
    page = data.get('page', 1)
    
    if not query:
        return jsonify({'status': 'error', 'message': 'No search query provided'})
    
    search_url = ''
    if engine == 'bing':
        search_url = f'https://www.bing.com/search?q={urllib.parse.quote(query)}&first={(page-1)*10+1}'
    elif engine == 'baidu':
        search_url = f'https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={(page-1)*10}'
    
    try:
        # 使用更完整的请求头，模拟正常浏览器行为
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.bing.com/' if engine == 'bing' else 'https://www.baidu.com/'
        }
        
        session = requests.Session()
        response = session.get(search_url, headers=headers, timeout=15, allow_redirects=True)
        
        # 处理可能的状态码
        if response.status_code == 403:
            # 尝试使用不同的User-Agent重试一次
            headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'
            response = session.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # 尝试确定正确的编码
            if response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding
                
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 提取搜索结果主体并直接显示
            html_content = str(soup)
            
            # Base URL for resolving relative links
            base_url = search_url
            
            # 处理搜索结果页面中的所有链接，改为通过我们的代理
            for link in soup.find_all(['a']):
                if link.has_attr('href'):
                    href = link['href']
                    # 跳过非导航链接
                    if href.startswith('javascript:') or href.startswith('#'):
                        continue
                    
                    # 处理相对URL
                    if not href.startswith(('http://', 'https://')):
                        # 处理相对路径
                        if href.startswith('/'):
                            # 域根目录的绝对路径
                            parsed_url = urllib.parse.urlparse(base_url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        else:
                            # 当前位置的相对路径
                            href = urllib.parse.urljoin(base_url, href)
                            
                    # 对搜索结果链接特殊处理
                    if engine == 'bing' and 'bing.com' in href and '/search?' in href:
                        # 这是必应内部搜索链接，提取查询参数并重定向到我们的搜索
                        parsed = urllib.parse.urlparse(href)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        if 'q' in query_params:
                            # 构建通过我们的应用进行搜索的JavaScript调用
                            link['href'] = f"javascript:searchBing('{query_params['q'][0]}')"
                            link['target'] = '_self'
                            continue
                    
                    elif engine == 'baidu' and 'baidu.com' in href and '/s?' in href:
                        # 这是百度内部搜索链接，提取查询参数并重定向到我们的搜索
                        parsed = urllib.parse.urlparse(href)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        if 'wd' in query_params:
                            # 构建通过我们的应用进行搜索的JavaScript调用
                            link['href'] = f"javascript:searchBaidu('{query_params['wd'][0]}')"
                            link['target'] = '_self'
                            continue
                            
                    # 对普通链接进行编码，通过我们的代理
                    encoded_url = base64.urlsafe_b64encode(href.encode()).decode()
                    link['href'] = f"javascript:loadUrl('{encoded_url}')"
                    link['target'] = '_self'  # 确保链接在同一窗口打开
            
            # 删除可能导致问题的脚本
            for script in soup.find_all('script'):
                script.decompose()
                
            # 对于必应，提取搜索结果区域
            content_area = None
            if engine == 'bing':
                content_area = soup.select_one('#b_content')
            elif engine == 'baidu':
                content_area = soup.select_one('#content_left')
                
            if content_area:
                search_html = str(content_area)
            else:
                # 如果找不到特定区域，使用整个文档
                search_html = str(soup.body) if soup.body else str(soup)
                
            # 判断是否有下一页
            has_next_page = False
            total_pages = 1
            
            if engine == 'bing':
                pagination = soup.select('.b_pag li a')
                if pagination:
                    for pager in pagination:
                        if pager.get_text() == '下一页' or pager.get_text() == 'Next':
                            has_next_page = True
                            break
                    
                    # 尝试估计总页数
                    page_nums = []
                    for pager in pagination:
                        if pager.get_text().isdigit():
                            page_nums.append(int(pager.get_text()))
                    
                    if page_nums:
                        total_pages = max(page_nums)
                    else:
                        total_pages = page + (1 if has_next_page else 0)
                        
            elif engine == 'baidu':
                pagination = soup.select('.page-inner a')
                if not pagination:
                    pagination = soup.select('.page-item a')  # 备选选择器
                    
                if pagination:
                    for pager in pagination:
                        if pager.get_text() == '下一页 >':
                            has_next_page = True
                            break
                    
                    # 估计总页数
                    page_nums = []
                    for pager in pagination:
                        if pager.get_text().isdigit():
                            page_nums.append(int(pager.get_text()))
                    
                    if page_nums:
                        total_pages = max(page_nums)
                    else:
                        total_pages = page + (1 if has_next_page else 0)
            
            # 添加一些自定义CSS以确保正确显示
            custom_style = """
                <style>
                    /* 重置容器样式 */
                    #search-results-wrapper {
                        background-color: white;
                        padding: 15px;
                        border-radius: 8px;
                        margin-bottom: 20px;
                    }
                    /* 修复百度页面布局 */
                    .s_form, .s_tab, #head, #foot, .sam_newgrid {
                        display: none !important;
                    }
                    /* 修复必应页面布局 */
                    .b_header, .b_footer, #id_h, #id_sc {
                        display: none !important;
                    }
                </style>
            """
            
            # 构建自定义搜索结果HTML
            final_html = f"""
                {custom_style}
                <div id="search-results-wrapper">
                    {search_html}
                </div>
                <script>
                    // 添加搜索功能的JavaScript
                    function searchBing(query) {{
                        window.searchProxy(query, 'bing');
                    }}
                    
                    function searchBaidu(query) {{
                        window.searchProxy(query, 'baidu');
                    }}
                </script>
            """
            
            # 将搜索结果中的数据提取为结构化格式（用于分页显示）
            results = []
            
            if engine == 'bing':
                for result in soup.select('.b_algo'):
                    link_element = result.select_one('h2 a')
                    if link_element:
                        title = link_element.get_text().strip()
                        href = link_element.get('href', '')
                        
                        # 获取摘要
                        snippet_element = result.select_one('.b_caption p')
                        snippet = snippet_element.get_text().strip() if snippet_element else ''
                        
                        results.append({
                            'title': title,
                            'url': href,
                            'snippet': snippet
                        })
            
            elif engine == 'baidu':
                for result in soup.select('.result, .c-container'):
                    link_element = result.select_one('h3.t a, .c-title a')
                    if link_element:
                        title = link_element.get_text().strip()
                        href = link_element.get('href', '')
                        
                        # 获取摘要
                        snippet_element = result.select_one('.c-abstract, .content-right_8Zs40')
                        snippet = snippet_element.get_text().strip() if snippet_element else ''
                        
                        results.append({
                            'title': title,
                            'url': href,
                            'snippet': snippet
                        })
            
            return jsonify({
                'status': 'success',
                'query': query,
                'results': results,
                'html': final_html,
                'engine': engine,
                'current_page': page,
                'total_pages': total_pages,
                'has_next_page': has_next_page,
                'search_url': search_url
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to perform search. Status code: {response.status_code}'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        })

@app.route('/decode_url', methods=['POST'])
def decode_url():
    data = request.json
    encoded_url = data.get('encoded_url')
    
    if not encoded_url:
        return jsonify({'status': 'error', 'message': 'No encoded URL provided'})
    
    try:
        decoded_url = base64.urlsafe_b64decode(encoded_url).decode()
        return jsonify({'status': 'success', 'url': decoded_url})
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'Failed to decode URL: {str(e)}'
        })

@app.route('/fetch_via_proxy', methods=['POST'])
def fetch_via_proxy():
    """使用第三方代理服务获取被拒绝的URL内容"""
    data = request.json
    url = data.get('url')
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # 尝试使用Allorigins作为代理
        # 这是一个开源的CORS代理，可以帮助绕过某些限制
        proxy_url = f'https://api.allorigins.win/raw?url={urllib.parse.quote(url)}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        }
        
        response = requests.get(proxy_url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            # 处理响应内容
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Base URL for resolving relative links
            base_url = url
            
            # Process links to make them go through our proxy
            for link in soup.find_all(['a', 'link']):
                if link.has_attr('href'):
                    href = link['href']
                    # Skip javascript, anchors, and other non-navigable links
                    if href.startswith('javascript:') or href.startswith('#'):
                        continue
                    
                    # Handle relative URLs
                    if not href.startswith(('http://', 'https://')):
                        # Handle relative paths
                        if href.startswith('/'):
                            # Absolute path from domain root
                            parsed_url = urllib.parse.urlparse(base_url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        else:
                            # Relative path from current location
                            href = urllib.parse.urljoin(base_url, href)
                    
                    # Encode URL to pass through our proxy
                    encoded_url = base64.urlsafe_b64encode(href.encode()).decode()
                    link['href'] = f"javascript:loadUrl('{encoded_url}')"
                    link['target'] = '_self'  # Ensure links open in the same window
            
            # Process forms to submit through our proxy
            for form in soup.find_all('form'):
                if form.has_attr('action'):
                    action = form['action']
                    if not action.startswith(('http://', 'https://')):
                        action = urllib.parse.urljoin(base_url, action)
                    
                    # Add a hidden input with the original action
                    hidden_input = soup.new_tag('input')
                    hidden_input['type'] = 'hidden'
                    hidden_input['name'] = '_proxy_original_action'
                    hidden_input['value'] = action
                    form.append(hidden_input)
                    
                    # Change the form to submit to our proxy
                    form['action'] = '/submit_form'
                    form['method'] = 'POST'
                    
                    # Add onsubmit handler to intercept form submission
                    form['onsubmit'] = "return interceptFormSubmit(this);"
            
            # Remove script and style elements that might contain text not meant for reading
            for script in soup(["script", "noscript", "svg"]):
                script.extract()
            
            # Get page title
            title = soup.title.string if soup.title else "Untitled Page"
            
            # Find text blocks
            blocks = []
            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'article', 'div', 'section']):
                if element.name in ['div', 'section'] and not element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5']):
                    continue
                
                text = element.get_text().strip()
                if len(text) > 50:  # Only consider substantial blocks of text
                    blocks.append({
                        'id': f'block-{len(blocks)}',
                        'text': text,
                        'tag': element.name,
                        'length': len(text)
                    })
            
            # Sort blocks by length to identify the main content
            blocks.sort(key=lambda x: x['length'], reverse=True)
            
            # Try to determine the main content block
            main_content_id = blocks[0]['id'] if blocks else None
            
            return jsonify({
                'status': 'success',
                'title': title,
                'url': url,
                'blocks': blocks,
                'main_content_id': main_content_id,
                'html': str(soup),
                'original_url': url,
                'via_proxy': True
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'代理服务请求失败: {response.status_code}'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'通过代理获取内容时发生错误: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False) 