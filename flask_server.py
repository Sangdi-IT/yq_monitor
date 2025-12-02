from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json
import re
from snownlp import SnowNLP
import jieba
from flask_cors import CORS
app = Flask(__name__)
CORS(app)


YUQING_KEYWORDS = ["投诉", "失望", "问题", "曝光", "维权", "负面", "危机", "事件", "不满", "愤怒"]

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def has_yuqing_keywords(text: str) -> bool:
    if not text:
        return False
    try:
        words = set(jieba.cut(text))
    except Exception:
        words = set(text.split())
    if any(kw in words for kw in YUQING_KEYWORDS):
        return True
    for kw in YUQING_KEYWORDS:
        if kw in text:
            return True
    return False

def analyze_sentiment(text: str, pos_thresh: float = 0.6, neg_thresh: float = 0.4):
    if not text:
        return "neutral", 0.5
    try:
        s = SnowNLP(text)
        score = float(s.sentiments)
    except Exception:
        return "neutral", 0.5
    if score > pos_thresh:
        return "positive", score
    elif score < neg_thresh:
        return "negative", score
    else:
        return "neutral", score

def parse_post_time(post):
    rt = post.get("readable_time") or post.get("readableTime") or post.get("readable")
    if rt and isinstance(rt, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(rt, fmt)
            except Exception:
                continue
    t = post.get("time")
    if isinstance(t, (int, float)):
        if t > 1e12:
            return datetime.fromtimestamp(t / 1000.0)
        elif t > 1e9:
            return datetime.fromtimestamp(t)
    return None

def is_recent(post_time, days: int = 100):
    if not post_time:
        return False
    try:
        return post_time >= (datetime.now() - timedelta(days=days))
    except Exception:
        return False
    
@app.route('/analyze', methods=['POST'])
def analyze_post():
    raw = request.get_json(force=True)
    post = raw.get("post", {})
    url = raw.get("url", "")
    items = post.get("items", [])
    if not items:
        return jsonify({"error": "No items found"}), 400

    item = items[0]
    note_card = item.get("note_card", {})
    title = note_card.get("title", "")
    content = note_card.get("desc", "")
    timestamp = note_card.get("time")
    location = note_card.get("ip_location", "")
    user_info = note_card.get("user", {})
    nickname = user_info.get("nickname", "")
    user_id = user_info.get("user_id", "")
    interact = note_card.get("interact_info", {})
    liked_count = interact.get("liked_count", "0")
    comment_count = interact.get("comment_count", "0")
    share_count = interact.get("share_count", "0")
    tags = note_card.get("tag_list", [])

    full_text = clean_text(f"{title} {content}")
    post_time = parse_post_time({"time": timestamp})
    sentiment, score = analyze_sentiment(full_text)
    has_keywords = has_yuqing_keywords(full_text)
    recent = is_recent(post_time)
    is_yuqing = (sentiment == "negative" or has_keywords) and recent
    
    # 构建结果字典
    result = {
        "is_yuqing": is_yuqing,
        "sentiment": sentiment,
        "sentiment_score": score,
        "has_yuqing_keywords": has_keywords,
        "cleaned_text": full_text,
        "parsed_time": post_time.strftime("%Y-%m-%d %H:%M:%S") if post_time else None,
        "title": title,
        "content": content,
        "timestamp": timestamp,
        "location": location,
        "user_nickname": nickname,
        "user_id": user_id,
        "liked_count": liked_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "tags": [tag.get("name") for tag in tags],
        "url": url,
        "human_verified": None  # None 表示未审核，true/false 表示人工判断结果
    }

    if is_yuqing:
        with open("yuqing_log.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return jsonify(result)
@app.route('/review', methods=['GET'])
def review_yuqing():
    results = []
    try:
        with open("yuqing_log.json", "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line.strip())
                    if item.get("human_verified") is not False:  # 只展示未审核或确认是舆情的
                        results.append(item)
                except Exception:
                    continue
    except FileNotFoundError:
        results = []
    return jsonify(results)
@app.route('/verify', methods=['POST'])
def verify_yuqing():
    data = request.get_json(force=True)
    url = data.get("url")
    is_yuqing = data.get("is_yuqing")  # 人工判断结果：True 或 False

    updated = []
    try:
        with open("yuqing_log.json", "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line.strip())
                if item.get("url") == url:
                    item["human_verified"] = is_yuqing
                updated.append(item)
        with open("yuqing_log.json", "w", encoding="utf-8") as f:
            for item in updated:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
