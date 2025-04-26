document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('errorMessage');
    const contentContainer = document.getElementById('contentContainer');
    const originalView = document.getElementById('originalView');
    const textView = document.getElementById('textView');
    const searchResults = document.getElementById('searchResults');
    const pageTitle = document.getElementById('pageTitle');
    const viewModeToggle = document.getElementById('viewModeToggle');
    const playButton = document.getElementById('playButton');
    const speedSelector = document.getElementById('speedSelector');
    
    // Speech synthesis variables
    let speech = null;
    let currentPlayingBlock = null;
    let isPlaying = false;
    
    // Current state variables
    let currentUrl = '';
    let currentQuery = '';
    let currentEngine = 'direct';
    let currentPage = 1;
    let totalPages = 1;
    let areaSelectionMode = false;
    
    // Area selection mode
    const selectionButton = document.getElementById('areaSelectionButton');
    let highlightedElement = null;
    let selectionOverlay = null;
    
    // Handle search/URL input
    searchButton.addEventListener('click', function() {
        const query = searchInput.value.trim();
        if (!query) return;
        
        currentEngine = document.querySelector('input[name="engine"]:checked').value;
        currentPage = 1;
        
        // Reset UI
        originalView.innerHTML = '';
        textView.innerHTML = '';
        searchResults.innerHTML = '';
        errorMessage.style.display = 'none';
        contentContainer.style.display = 'none';
        loading.style.display = 'block';
        
        if (currentEngine === 'direct') {
            currentUrl = query;
            fetchUrl(query);
        } else {
            currentQuery = query;
            searchContent(query, currentEngine, currentPage);
        }
    });
    
    // Allow pressing Enter to search
    searchInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            searchButton.click();
        }
    });
    
    // Toggle between original and text-only view
    viewModeToggle.addEventListener('click', function() {
        if (originalView.style.display !== 'none') {
            originalView.style.display = 'none';
            textView.style.display = 'block';
            viewModeToggle.textContent = '原网页模式';
        } else {
            originalView.style.display = 'block';
            textView.style.display = 'none';
            viewModeToggle.textContent = '仅文字模式';
        }
    });
    
    // Handle play button
    playButton.addEventListener('click', function() {
        if (isPlaying) {
            stopSpeech();
            playButton.textContent = '🔊 朗读内容';
            isPlaying = false;
        } else {
            const blocks = document.querySelectorAll('.block');
            if (blocks.length > 0) {
                // Find main content block (first one by default)
                let blockToPlay = blocks[0];
                const mainContentBlock = document.querySelector('[data-main-content="true"]');
                
                if (mainContentBlock) {
                    blockToPlay = mainContentBlock;
                }
                
                playSpeech(blockToPlay);
            }
        }
    });
    
    // Handle speed change
    speedSelector.addEventListener('change', function() {
        if (speech) {
            speech.rate = parseFloat(this.value);
        }
    });
    
    // Area selection mode toggle
    if (selectionButton) {
        selectionButton.addEventListener('click', function() {
            toggleAreaSelectionMode();
        });
    }
    
    // Function to toggle area selection mode
    function toggleAreaSelectionMode() {
        areaSelectionMode = !areaSelectionMode;
        
        // Find help tip element
        const helpTip = document.querySelector('.selection-help-tip');
        
        if (areaSelectionMode) {
            // Enable selection mode
            selectionButton.classList.add('active');
            selectionButton.textContent = '取消选择';
            
            // Show help tip
            if (helpTip) {
                helpTip.style.display = 'block';
            }
            
            // Create overlay for selection feedback if not exists
            if (!selectionOverlay) {
                selectionOverlay = document.createElement('div');
                selectionOverlay.className = 'selection-overlay';
                selectionOverlay.style.position = 'absolute';
                selectionOverlay.style.border = '2px solid yellow';
                selectionOverlay.style.backgroundColor = 'rgba(255, 255, 0, 0.2)';
                selectionOverlay.style.pointerEvents = 'none';
                selectionOverlay.style.zIndex = '1000';
                selectionOverlay.style.display = 'none';
                selectionOverlay.style.transition = 'all 0.1s ease-out';
                document.body.appendChild(selectionOverlay);
            } else {
                selectionOverlay.style.display = 'none';
            }
            
            // Add event listeners for mouse
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('click', handleElementSelection);
            
            // Add event listeners for touch devices
            document.addEventListener('touchmove', handleTouchMove, { passive: false });
            document.addEventListener('touchend', handleTouchEnd);
            
            // Disable scrolling while in selection mode (for original view only)
            document.body.style.overflow = originalView.style.display !== 'none' 
                ? 'hidden' : 'auto';
            
            // Show helper message
            showMessage('移动鼠标或手指至内容区域，点击或触摸选择要朗读的区域');
        } else {
            // Disable selection mode
            selectionButton.classList.remove('active');
            selectionButton.textContent = '选择朗读区域';
            
            // Hide help tip
            if (helpTip) {
                helpTip.style.display = 'none';
            }
            
            // Remove event listeners
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('click', handleElementSelection);
            document.removeEventListener('touchmove', handleTouchMove);
            document.removeEventListener('touchend', handleTouchEnd);
            
            // Hide overlay
            if (selectionOverlay) {
                selectionOverlay.style.display = 'none';
            }
            
            // Re-enable scrolling
            document.body.style.overflow = 'auto';
            
            // Clear any message
            hideMessage();
        }
    }
    
    // Find the best element to highlight based on content and size
    function findBestElement(element, minSize = 100) {
        if (!element) return null;
        
        // Skip tiny elements and those with no text content
        const rect = element.getBoundingClientRect();
        if (rect.width < minSize || rect.height < minSize) {
            return element.parentElement;
        }
        
        // Skip elements with very little text
        const text = element.textContent?.trim() || '';
        if (text.length < 50 && element.parentElement) {
            return element.parentElement;
        }
        
        // Skip certain element types that usually don't contain readable content
        const tagName = element.tagName.toLowerCase();
        if (['svg', 'button', 'input', 'img', 'a'].includes(tagName) && element.parentElement) {
            return element.parentElement;
        }
        
        return element;
    }
    
    // Find the most appropriate content container
    function findContentContainer(element, maxLevels = 3) {
        let currentElement = element;
        let bestElement = element;
        let bestTextLength = element.textContent?.trim().length || 0;
        let level = 0;
        
        // Move up the DOM tree looking for elements with more text
        while (currentElement && level < maxLevels) {
            const parent = currentElement.parentElement;
            if (!parent) break;
            
            // Check if parent has significantly more text
            const parentTextLength = parent.textContent?.trim().length || 0;
            if (parentTextLength > bestTextLength * 1.5) {
                bestElement = parent;
                bestTextLength = parentTextLength;
            }
            
            currentElement = parent;
            level++;
        }
        
        return bestElement;
    }
    
    // Handle mouse movement for area selection
    function handleMouseMove(e) {
        if (!areaSelectionMode) return;
        
        // Get element under the mouse
        const element = document.elementFromPoint(e.clientX, e.clientY);
        
        // Only consider elements in the content area
        if (element && (originalView.contains(element) || textView.contains(element))) {
            // Get the best element to highlight
            const targetElement = findBestElement(element);
            const contentContainer = findContentContainer(targetElement);
            
            // Update highlighted element
            if (contentContainer !== highlightedElement) {
                highlightedElement = contentContainer;
                
                // Update overlay position and dimensions
                updateSelectionOverlay(highlightedElement);
            }
        } else {
            // Hide overlay if not over a valid element
            if (selectionOverlay) {
                selectionOverlay.style.display = 'none';
            }
            highlightedElement = null;
        }
    }
    
    // Handle touch movement for area selection
    function handleTouchMove(e) {
        if (!areaSelectionMode) return;
        
        // Prevent scrolling while in selection mode
        e.preventDefault();
        
        if (e.touches && e.touches[0]) {
            const touch = e.touches[0];
            
            // Get element under the touch
            const element = document.elementFromPoint(touch.clientX, touch.clientY);
            
            // Only consider elements in the content area
            if (element && (originalView.contains(element) || textView.contains(element))) {
                // Get the best element to highlight
                const targetElement = findBestElement(element);
                const contentContainer = findContentContainer(targetElement);
                
                // Update highlighted element
                if (contentContainer !== highlightedElement) {
                    highlightedElement = contentContainer;
                    
                    // Update overlay position and dimensions
                    updateSelectionOverlay(highlightedElement);
                }
            } else {
                // Hide overlay if not over a valid element
                if (selectionOverlay) {
                    selectionOverlay.style.display = 'none';
                }
                highlightedElement = null;
            }
        }
    }
    
    // Update selection overlay position and dimensions
    function updateSelectionOverlay(element) {
        if (!element || !selectionOverlay) return;
        
        const rect = element.getBoundingClientRect();
        
        // Make the overlay visible
        selectionOverlay.style.display = 'block';
        selectionOverlay.style.top = (rect.top + window.scrollY) + 'px';
        selectionOverlay.style.left = (rect.left + window.scrollX) + 'px';
        selectionOverlay.style.width = rect.width + 'px';
        selectionOverlay.style.height = rect.height + 'px';
    }
    
    // Handle element selection via mouse click
    function handleElementSelection(e) {
        if (!areaSelectionMode || !highlightedElement) return;
        
        // Read the content of the selected element
        readSelectedElement(highlightedElement);
    }
    
    // Handle element selection via touch end
    function handleTouchEnd(e) {
        if (!areaSelectionMode || !highlightedElement) return;
        
        // Read the content of the selected element
        readSelectedElement(highlightedElement);
    }
    
    // Read the selected element content
    function readSelectedElement(element) {
        const text = element.textContent.trim();
        if (text) {
            // Create a virtual block element for the speech function
            const virtualBlock = document.createElement('div');
            virtualBlock.textContent = text;
            
            // Play the speech
            playSpeech(virtualBlock);
            
            // Exit selection mode
            toggleAreaSelectionMode();
        }
    }
    
    // Function to fetch and process URL
    function fetchUrl(url) {
        loading.style.display = 'block';
        
        fetch('/fetch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url }),
        })
        .then(response => response.json())
        .then(data => {
            loading.style.display = 'none';
            
            if (data.status === 'success') {
                contentContainer.style.display = 'block';
                searchResults.style.display = 'none';
                originalView.style.display = 'block';
                textView.style.display = 'none';
                
                // Set page title
                pageTitle.textContent = data.title;
                document.title = data.title + ' - 网页朗读助手';
                
                // Update current URL
                currentUrl = data.url;
                
                // Display original content
                originalView.innerHTML = data.html;
                
                // Process and display text blocks
                textView.innerHTML = '';
                data.blocks.forEach((block, index) => {
                    const blockDiv = document.createElement('div');
                    blockDiv.className = 'block';
                    blockDiv.id = block.id;
                    blockDiv.textContent = block.text;
                    
                    // Mark main content block
                    if (block.id === data.main_content_id) {
                        blockDiv.setAttribute('data-main-content', 'true');
                        blockDiv.classList.add('active-block');
                    }
                    
                    // Add click event to play this block
                    blockDiv.addEventListener('click', function() {
                        playSpeech(this);
                    });
                    
                    textView.appendChild(blockDiv);
                });
                
                // Add interceptFormSubmit script to the page
                setupFormInterception();
            } else {
                // 错误处理
                if (data.message && data.message.includes('Status code: 403')) {
                    // 403 Forbidden 错误 - 尝试通过代理访问
                    showMessage('网站拒绝直接访问，正在尝试通过代理获取内容...');
                    fetchViaProxy(url);
                } else {
                    showError(data.message);
                }
            }
        })
        .catch(error => {
            loading.style.display = 'none';
            showError('发生错误: ' + error.message);
        });
    }
    
    // 通过代理获取内容
    function fetchViaProxy(url) {
        loading.style.display = 'block';
        
        fetch('/fetch_via_proxy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url }),
        })
        .then(response => response.json())
        .then(data => {
            loading.style.display = 'none';
            hideMessage(); // 关闭提示信息
            
            if (data.status === 'success') {
                contentContainer.style.display = 'block';
                searchResults.style.display = 'none';
                originalView.style.display = 'block';
                textView.style.display = 'none';
                
                // Set page title
                pageTitle.textContent = data.title + ' (通过代理加载)';
                document.title = data.title + ' - 网页朗读助手';
                
                // Update current URL
                currentUrl = data.url;
                
                // Display original content
                originalView.innerHTML = data.html;
                
                // Process and display text blocks
                textView.innerHTML = '';
                data.blocks.forEach((block, index) => {
                    const blockDiv = document.createElement('div');
                    blockDiv.className = 'block';
                    blockDiv.id = block.id;
                    blockDiv.textContent = block.text;
                    
                    // Mark main content block
                    if (block.id === data.main_content_id) {
                        blockDiv.setAttribute('data-main-content', 'true');
                        blockDiv.classList.add('active-block');
                    }
                    
                    // Add click event to play this block
                    blockDiv.addEventListener('click', function() {
                        playSpeech(this);
                    });
                    
                    textView.appendChild(blockDiv);
                });
                
                // Add interceptFormSubmit script to the page
                setupFormInterception();
                
                // 显示通过代理成功的提示
                showMessage('内容通过代理成功加载');
                setTimeout(hideMessage, 3000);
            } else {
                showError('通过代理获取内容失败: ' + data.message + '<br><br>您可以尝试访问其他网站或稍后再试。');
            }
        })
        .catch(error => {
            loading.style.display = 'none';
            hideMessage();
            showError('通过代理获取内容时发生错误: ' + error.message);
        });
    }
    
    // Function to search content using search engines
    function searchContent(query, engine, page = 1) {
        // 显示加载中
        loading.style.display = 'block';
        contentContainer.style.display = 'none';
        
        fetch('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: query,
                engine: engine,
                page: page
            }),
        })
        .then(response => response.json())
        .then(data => {
            loading.style.display = 'none';
            
            if (data.status === 'success') {
                contentContainer.style.display = 'block';
                searchResults.style.display = 'block';
                originalView.style.display = 'none';
                textView.style.display = 'none';
                
                // Update current state
                currentQuery = data.query;
                currentEngine = data.engine;
                currentPage = data.current_page;
                totalPages = data.total_pages;
                
                // Set page title
                pageTitle.textContent = `搜索: ${data.query} (第 ${currentPage}/${totalPages} 页)`;
                document.title = `搜索: ${data.query} - 网页朗读助手`;
                
                // 直接显示完整的搜索结果HTML
                searchResults.innerHTML = data.html;
                
                // 添加分页控件
                const paginationDiv = document.createElement('div');
                paginationDiv.className = 'pagination';
                
                // Previous page button
                if (currentPage > 1) {
                    const prevButton = document.createElement('button');
                    prevButton.className = 'pagination-button';
                    prevButton.textContent = '上一页';
                    prevButton.addEventListener('click', function() {
                        searchContent(currentQuery, currentEngine, currentPage - 1);
                    });
                    paginationDiv.appendChild(prevButton);
                }
                
                // Page numbers
                const pageInfo = document.createElement('span');
                pageInfo.className = 'page-info';
                pageInfo.textContent = `${currentPage} / ${totalPages}`;
                paginationDiv.appendChild(pageInfo);
                
                // Next page button
                if (data.has_next_page) {
                    const nextButton = document.createElement('button');
                    nextButton.className = 'pagination-button';
                    nextButton.textContent = '下一页';
                    nextButton.addEventListener('click', function() {
                        searchContent(currentQuery, currentEngine, currentPage + 1);
                    });
                    paginationDiv.appendChild(nextButton);
                }
                
                searchResults.appendChild(paginationDiv);
                
                // 使搜索引擎的内部搜索功能工作
                window.searchProxy = function(query, engine) {
                    searchContent(query, engine, 1);
                };
            } else {
                showError(data.message);
            }
        })
        .catch(error => {
            loading.style.display = 'none';
            showError('发生错误: ' + error.message);
        });
    }
    
    // Setup form interception
    function setupFormInterception() {
        // Add a script element to define the interceptFormSubmit function
        const scriptElement = document.createElement('script');
        scriptElement.textContent = `
            function interceptFormSubmit(form) {
                // This function will be called when a form is submitted
                console.log('Form submission intercepted');
                return true; // Allow the form to submit
            }
        `;
        document.head.appendChild(scriptElement);
    }
    
    // Function to load URL from encoded data
    window.loadUrl = function(encodedUrl) {
        fetch('/decode_url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ encoded_url: encodedUrl }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                fetchUrl(data.url);
            } else {
                showError(data.message);
            }
        })
        .catch(error => {
            showError('解码URL时发生错误: ' + error.message);
        });
    };
    
    // Function to play speech for a block
    function playSpeech(blockElement) {
        // Stop any current speech
        stopSpeech();
        
        // Remove active class from all blocks
        document.querySelectorAll('.block').forEach(block => {
            block.classList.remove('active-block');
        });
        
        // Add active class to current block if it's in the DOM
        if (blockElement.parentNode) {
            blockElement.classList.add('active-block');
        }
        
        // Get text content and create speech
        const text = blockElement.textContent;
        speech = new SpeechSynthesisUtterance(text);
        
        // Set speech properties
        speech.lang = 'zh-CN';
        speech.rate = parseFloat(speedSelector.value);
        speech.onend = function() {
            isPlaying = false;
            playButton.textContent = '🔊 朗读内容';
            if (blockElement.parentNode) {
                blockElement.classList.remove('active-block');
            }
        };
        
        // Start speaking
        window.speechSynthesis.speak(speech);
        isPlaying = true;
        playButton.textContent = '⏹ 停止朗读';
        currentPlayingBlock = blockElement;
    }
    
    // Function to stop speech
    function stopSpeech() {
        if (speech) {
            window.speechSynthesis.cancel();
            
            if (currentPlayingBlock && currentPlayingBlock.parentNode) {
                currentPlayingBlock.classList.remove('active-block');
            }
        }
    }
    
    // Function to show error message
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        contentContainer.style.display = 'none';
    }
    
    // Function to show a temporary message
    function showMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-overlay';
        messageDiv.textContent = message;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '50%';
        messageDiv.style.left = '50%';
        messageDiv.style.transform = 'translate(-50%, -50%)';
        messageDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        messageDiv.style.color = 'white';
        messageDiv.style.padding = '15px 20px';
        messageDiv.style.borderRadius = '5px';
        messageDiv.style.zIndex = '2000';
        messageDiv.id = 'tempMessage';
        document.body.appendChild(messageDiv);
    }
    
    // Function to hide temporary message
    function hideMessage() {
        const message = document.getElementById('tempMessage');
        if (message) {
            message.remove();
        }
    }
}); 