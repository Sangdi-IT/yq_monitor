import json
from datetime import datetime, timedelta
import re
from snownlp import SnowNLP
import jieba
import argparse
import os
from typing import Optional, Tuple, Dict, Any, List

# 定义舆情关键词列表（可自定义，针对负面或敏感话题）
YUQING_KEYWORDS = ["投诉", "失望", "问题", "曝光", "维权", "负面", "危机", "事件", "不满", "愤怒"]

def clean_text(text: str) -> str:
    """简单清洗文本：移除 URL、表情、多余空格"""
    if not text:
        return ""
    text = re.sub(r'http[s]?://\S+', '', text)  # 移除 URL
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s]', '', text)  # 移除特殊字符/表情
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def has_yuqing_keywords(text: str) -> bool:
    """检查是否包含舆情关键词：分词 + 子串匹配以提高命中率"""
    if not text:
        return False
    try:
        words = set(jieba.cut(text))
    except Exception:
        words = set(text.split())
    # 分词匹配
    if any(kw in words for kw in YUQING_KEYWORDS):
        return True
    # 子串匹配（补充）
    for kw in YUQING_KEYWORDS:
        if kw in text:
            return True
    return False

def analyze_sentiment(text: str, pos_thresh: float = 0.6, neg_thresh: float = 0.4) -> Tuple[str, float]:
    """使用 SnowNLP 进行情感分析，异常时返回 neutral"""
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

def parse_post_time(post: Dict[str, Any]) -> Optional[datetime]:
    """尝试从 post 中解析时间，支持 readable_time 和数值 time（毫秒/秒）"""
    rt = post.get("readable_time") or post.get("readableTime") or post.get("readable")
    if rt and isinstance(rt, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(rt, fmt)
            except Exception:
                continue
    t = post.get("time")
    if isinstance(t, (int, float)):
        # 判断是毫秒还是秒
        if t > 1e12:
            return datetime.fromtimestamp(t / 1000.0)
        elif t > 1e9:
            return datetime.fromtimestamp(t)
    return None

def is_recent(post_time: Optional[datetime], days: int = 1) -> bool:
    """检查发布时间是否在最近 days 天内"""
    if not post_time:
        return False
    try:
        return post_time >= (datetime.now() - timedelta(days=days))
    except Exception:
        return False

def process_posts(input_file: str,
                  output_file: str,
                  days: int = 1,
                  pos_thresh: float = 0.6,
                  neg_thresh: float = 0.4) -> None:
    """主处理函数：读取 JSON，分析并输出舆情帖子"""
    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            posts = json.load(f)
    except Exception as e:
        print(f"读取 JSON 失败: {e}")
        return

    yuqing_posts: List[Dict[str, Any]] = []
    stats = {"total": 0, "yuqing_count": 0, "negative": 0, "neutral": 0, "positive": 0}

    for post in posts:
        title = post.get("unified_title", "") or post.get("title", "")
        desc = post.get("desc", "") or post.get("content", "")
        full_text = clean_text(f"{title} {desc}").strip()
        if not full_text:
            continue

        sentiment, score = analyze_sentiment(full_text, pos_thresh=pos_thresh, neg_thresh=neg_thresh)
        has_keywords = has_yuqing_keywords(full_text)
        post_time = parse_post_time(post)
        recent = is_recent(post_time, days=days)

        is_yuqing = (sentiment == "negative" or has_keywords) and recent

        post["cleaned_text"] = full_text
        post["sentiment"] = sentiment
        post["sentiment_score"] = score
        post["has_yuqing_keywords"] = has_keywords
        post["is_yuqing"] = is_yuqing
        if post_time:
            post["parsed_time"] = post_time.strftime("%Y-%m-%d %H:%M:%S")

        stats["total"] += 1
        stats[sentiment] = stats.get(sentiment, 0) + 1
        if is_yuqing:
            stats["yuqing_count"] += 1
            yuqing_posts.append(post)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(yuqing_posts, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入输出文件失败: {e}")
        return

    total = stats["total"] or 1
    print(f"处理完成！总帖子: {stats['total']}")
    print(f"舆情帖子: {stats['yuqing_count']} ({stats['yuqing_count']/total*100:.2f}%)")
    print(f"情感分布: 正面 {stats['positive']}, 中性 {stats['neutral']}, 负面 {stats['negative']}")
    print(f"输出文件: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="舆情情感分析脚本")
    parser.add_argument("-i", "--input", required=False, default="yq_monitor.json", help="输入 JSON 文件路径（默认 redbook.json）")
    parser.add_argument("-o", "--output", required=False, default="yuqing_posts.json", help="输出舆情 JSON 文件路径（默认 yuqing_posts.json）")
    parser.add_argument("-d", "--days", type=int, default=1, help="判断为近期的天数（默认1天）")
    parser.add_argument("--pos", type=float, default=0.6, help="正面阈值（默认0.6）")
    parser.add_argument("--neg", type=float, default=0.4, help="负面阈值（默认0.4）")
    args = parser.parse_args()

    process_posts(args.input, args.output, days=args.days, pos_thresh=args.pos, neg_thresh=args.neg)

if __name__ == "__main__":
    main()