let isRunning = false;
const clickedIndexes = new Set();
let clickInterval = 1000;

// 创建提示元素
const createPrompt = () => {
	const prompt = document.createElement('div');
	prompt.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 20px;
        border-radius: 8px;
        z-index: 10000;
        font-size: 16px;
        text-align: center;
    `;
	prompt.textContent = '当前内容已处理完毕，请滚动页面加载更多内容';
	return prompt;
};

// 延时函数
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

// 等待元素出现的函数
async function waitForElement(selector, timeout = 1000) {
	const startTime = Date.now();
	while (Date.now() - startTime < timeout) {
		const element = document.querySelector(selector);
		if (element) return element;
		await delay(100);
	}
	return null;
}

// 改进的页面滚动函数
async function scrollPage() {
	const initialHeight = document.body.scrollHeight;

	// 滚动到页面底部
	window.scrollTo(0, document.body.scrollHeight);

	// 等待新内容加载
	await delay(1000);

	// 检查是否成功加载了新内容
	const newHeight = document.body.scrollHeight;
	return newHeight > initialHeight;
}

// 检查是否所有可见元素都已点击
function allVisibleElementsClicked() {
	const covers = document.querySelectorAll('.cover.ld.mask');
	let allClicked = true;
	let hasVisibleElements = false;

	for (let cover of covers) {
		const noteItem = cover.closest('.note-item');
		if (!noteItem) continue;

		const dataIndex = noteItem.getAttribute('data-index');
		if (window.getComputedStyle(cover).display !== 'none') {
			hasVisibleElements = true;
			if (!clickedIndexes.has(dataIndex)) {
				allClicked = false;
				break;
			}
		}
	}

	return hasVisibleElements && allClicked;
}

// 查找下一个可点击的元素
function findNextClickableElement() {
	const covers = document.querySelectorAll('.cover.ld.mask');
	console.log('找到covers元素数量:', covers.length);

	for (let [index, cover] of covers.entries()) {
		const noteItem = cover.closest('.note-item');
		if (!noteItem) continue;

		const dataIndex = noteItem.getAttribute('data-index');
		if (clickedIndexes.has(dataIndex)) continue;

		if (window.getComputedStyle(cover).display !== 'none') {
			return { cover, dataIndex };
		}
	}
	return null;
}

// 点击处理函数
async function handleClick(cover, dataIndex) {
	clickedIndexes.add(dataIndex);
	console.log(`点击 data-index: ${dataIndex}，当前已点击数量：${clickedIndexes.size}`);

	cover.click();
	console.log('点击了封面');

	chrome.runtime.sendMessage({ type: 'CLICK_COUNT' });

	await delay(2000);

	console.log('等待关闭按钮出现...');
	const closeButton = await waitForElement('.close-circle');
	if (closeButton) {
		console.log('找到关闭按钮，准备关闭');
		closeButton.click();
		console.log('点击关闭按钮');
		await delay(500);
	} else {
		console.log('未能找到关闭按钮，尝试备用方案');
		const mask = document.querySelector('.note-detail-mask');
		if (mask) {
			console.log('尝试点击蒙层关闭');
			mask.click();
			await delay(500);
		}
	}
}

// 导出HAR文件
async function exportHAR(filename) {
	try {
		// 使用CDP获取HAR数据
		const harData = await chrome.debugger.sendCommand({
			target: { tabId: chrome.devtools.inspectedWindow.tabId }
		}, 'Network.getHAR');

		// 过滤只包含feed的请求
		if (harData && harData.log && Array.isArray(harData.log.entries)) {
			harData.log.entries = harData.log.entries.filter(entry => {
				return entry.request.url.toLowerCase().includes('feed');
			});
		}

		// 创建Blob对象
		const blob = new Blob([JSON.stringify(harData, null, 2)], { type: 'application/json' });

		// 创建下载链接
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename || 'network-log.har';

		// 触发下载
		document.body.appendChild(a);
		a.click();

		// 清理
		document.body.removeChild(a);
		URL.revokeObjectURL(url);

		console.log('HAR文件导出成功');
	} catch (error) {
		console.error('导出HAR文件失败:', error);
	}
}

// 主循环
async function startClickingLoop() {
	// 开始记录网络请求
	try {
		await chrome.debugger.attach({ tabId: chrome.devtools.inspectedWindow.tabId }, '1.3');
		await chrome.debugger.sendCommand({
			target: { tabId: chrome.devtools.inspectedWindow.tabId }
		}, 'Network.enable');
	} catch (error) {
		console.error('启用网络请求记录失败:', error);
	}

	while (isRunning) {
		const nextElement = findNextClickableElement();

		if (nextElement) {
			await handleClick(nextElement.cover, nextElement.dataIndex);
			await delay(clickInterval);
		} else if (allVisibleElementsClicked()) {
			console.log('当前视图元素已处理完毕，尝试滚动');

			const scrolled = await scrollPage();

			if (!scrolled) {
				console.log('已到达底部或无法滚动，停止处理');
				isRunning = false;
				break;
			} else {
				console.log('滚动成功，等待新内容加载');
				await delay(1000);
			}
		} else {
			await delay(1000);
		}
	}
}

// 监听来自popup的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
	console.log('收到消息:', request);

	if (request.type === 'START_CLICKING' && !isRunning) {
		console.log('开始点击操作');
		console.log('已点击的索引:', Array.from(clickedIndexes));
		isRunning = true;
		if (request.interval) {
			clickInterval = request.interval;
		}
		startClickingLoop();
	} else if (request.type === 'STOP_CLICKING') {
		console.log('停止点击操作');
		console.log('已点击的索引:', Array.from(clickedIndexes));
		isRunning = false;
	}
});

// 初始化MutationObserver
const observer = new MutationObserver((mutations) => {
	for (let mutation of mutations) {
		if (mutation.type === 'childList' ||
			(mutation.type === 'attributes' && mutation.attributeName === 'data-index')) {
			// 新元素加载的处理
		}
	}
});

function initializeObserver() {
	const container = document.querySelector('.feeds-container');
	if (container) {
		observer.observe(container, {
			childList: true,
			subtree: true,
			attributes: true,
			attributeFilter: ['data-index']
		});
		console.log('观察器已初始化');
	}
}

// 初始化
if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', initializeObserver);
} else {
	initializeObserver();
}


// 错误处理
window.addEventListener('error', (event) => {
	console.error('捕获到错误:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
	console.error('未处理的Promise拒绝:', event.reason);
});