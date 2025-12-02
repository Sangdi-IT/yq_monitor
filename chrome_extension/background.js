// 存储网络请求
let networkRequests = [];
let isCapturing = false;

// 监听网络请求
chrome.webRequest.onCompleted.addListener(
	function (details) {
		if (isCapturing && details.url.toLowerCase().includes('feed')) {
			networkRequests.push({
				url: details.url,
				method: details.method,
				timeStamp: details.timeStamp,
				type: details.type,
				statusCode: details.statusCode,
				statusLine: details.statusLine
			});
		}
	},
	{ urls: ["<all_urls>"] }
);

// 监听来自content script的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
	if (request.action === 'START_CAPTURE') {
		networkRequests = [];
		isCapturing = true;
		sendResponse({ status: 'started' });
	}
	else if (request.action === 'STOP_CAPTURE') {
		isCapturing = false;
		// 导出HAR文件
		const har = {
			log: {
				version: '1.2',
				creator: {
					name: 'Feed Capture Extension',
					version: '1.0'
				},
				pages: [],
				entries: networkRequests.map(request => ({
					startedDateTime: new Date(request.timeStamp).toISOString(),
					request: {
						method: request.method,
						url: request.url
					},
					response: {
						status: request.statusCode,
						statusText: request.statusLine
					}
				}))
			}
		};

		const blob = new Blob([JSON.stringify(har, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);

		chrome.downloads.download({
			url: url,
			filename: `feed-requests-${new Date().toISOString().replace(/:/g, '-')}.har`,
			saveAs: false
		}, () => {
			URL.revokeObjectURL(url);
		});

		sendResponse({ status: 'completed', count: networkRequests.length });
	}
	return true;
});