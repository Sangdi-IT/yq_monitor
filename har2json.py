import json
import base64
from typing import Dict, List, Union, Any, Optional
import os
import sys
from datetime import datetime
import zoneinfo  # For timezone handling (Python 3.9+)

class HarExtractor:
    def __init__(self, har_file: str):
        self.har_file = har_file
        self.content_list = []
        print(f"\n初始化 HAR 提取器... 目标文件: {har_file}")

    def decode_base64_content(self, content: str) -> str:
        try:
            padding = 4 - (len(content) % 4)
            if padding != 4:
                content += '=' * padding
            return base64.b64decode(content).decode('utf-8')
        except Exception as e:
            print(f"Base64 解码失败: {str(e)}")
            return content

    def extract_note_cards(self, content: Any) -> List[Dict]:
        note_cards = []
        try:
            if isinstance(content, dict):
                items = content.get('data', {}).get('items', [])
                note_cards = [item['note_card'] for item in items if item.get('model_type') == 'note' and 'note_card' in item]
        except Exception as e:
            print(f"提取 note_card 时发生错误: {str(e)}")
        return note_cards

    def process_content(self, content_text: str, url: str) -> List[Dict]:
        try:
            parsed_content = json.loads(content_text)
        except json.JSONDecodeError:
            try:
                decoded_content = self.decode_base64_content(content_text)
                parsed_content = json.loads(decoded_content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"警告: URL {url} 的内容既不是有效的 JSON 也不是有效的 base64，将跳过")
                return []
        return self.extract_note_cards(parsed_content)

    def unify_titles(self) -> None:
        for note in self.content_list:
            note['unified_title'] = note.get('display_title') or note.get('title') or ''

    def convert_timestamps(self) -> None:
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")  # Beijing time (UTC+8)
        for note in self.content_list:
            for field, readable_field in [('time', 'readable_time'), ('current_time', 'readable_current_time')]:
                if field in note:
                    try:
                        timestamp_ms = int(note[field])
                        timestamp_s = timestamp_ms / 1000
                        dt_utc = datetime.fromtimestamp(timestamp_s, tz=zoneinfo.ZoneInfo("UTC"))
                        dt_local = dt_utc.astimezone(tz)
                        note[readable_field] = dt_local.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        print(f"警告: 无法转换 '{field}' 字段: {note.get(field)}")

    def extract_content(self) -> List[Dict[str, Any]]:
        print("\n开始提取内容...")
        har_data = self.read_har_file()
        entries = har_data.get('log', {}).get('entries', [])
        print(f"找到 {len(entries)} 个请求记录")
        
        for entry in entries:
            # Unified handling for both formats
            content = entry.get('content') or entry.get('response', {}).get('content', {})
            url = entry.get('url') or entry.get('request', {}).get('url', '')
            if content and 'text' in content:
                note_cards = self.process_content(content['text'], url)
                if note_cards:
                    self.content_list.extend(note_cards)
                    print(f"成功提取 URL: {url} 的 {len(note_cards)} 个笔记")
        
        self.unify_titles()
        self.convert_timestamps()
        print(f"\n内容提取完成！共提取了 {len(self.content_list)} 个内容项")
        return self.content_list

    def read_har_file(self) -> Dict:
        print("正在读取 HAR 文件...")
        try:
            with open(self.har_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"读取 HAR 文件失败: {str(e)}")

    def save_to_json(self, output_file: str = None) -> str:
        if not self.content_list:
            raise Exception("没有要保存的内容，请先调用 extract_content()")
        
        if output_file is None:
            base_name = os.path.splitext(os.path.basename(self.har_file))[0]
            output_file = f"{base_name}_content.json"
        
        print(f"\n正在保存内容到文件: {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.content_list, f, ensure_ascii=False, indent=2)
            print("文件保存成功！")
            return output_file
        except Exception as e:
            raise Exception(f"保存 JSON 文件失败: {str(e)}")

def process_har_file(har_file: str, output_file: str = None) -> Dict[str, Any]:
    start_time = datetime.now()
    try:
        extractor = HarExtractor(har_file)
        content_list = extractor.extract_content()
        output_path = extractor.save_to_json(output_file)
        processing_time = (datetime.now() - start_time).total_seconds()
        return {
            'success': True,
            'message': f'成功提取 {len(content_list)} 个内容项',
            'output_file': output_path,
            'content_count': len(content_list),
            'processing_time': processing_time
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'output_file': None,
            'content_count': 0
        }

def main():
    print("\n=== HAR 文件内容提取工具 ===")
    
    while True:
        har_path = input("\n请输入HAR文件路径: ").strip()
        if har_path and os.path.exists(har_path) and har_path.lower().endswith('.har'):
            break
        print("错误：无效的 HAR 文件路径")

    output_path = input("\n请输入输出文件路径（直接回车使用默认路径）: ").strip() or None
    if output_path and not output_path.lower().endswith('.json'):
        output_path += '.json'

    print("\n开始处理...")
    result = process_har_file(har_path, output_path)
    
    print("\n=== 处理结果 ===")
    if result['success']:
        print(f"状态: 成功\n输出文件: {result['output_file']}\n提取内容数: {result['content_count']}\n处理时间: {result['processing_time']:.2f} 秒")
    else:
        print(f"状态: 失败\n错误信息: {result['message']}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序发生错误: {str(e)}")
        sys.exit(1)
    finally:
        print("\n程序结束")