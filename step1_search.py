# YOUTUBE_API_KEY = "AIzaSyBE1Q3uPePfIiaImcD8EcVD3jo4dcqTp-I"

"""
YouTube视频搜索 - 第一步：获取列表并导出CSV
"""

import os
import csv
import time
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============================================================================
# 配置部分
# ============================================================================

# 🔑 重要：请用你的新API Key替换这里（已撤销旧的）
YOUTUBE_API_KEY = "AIzaSyBE1Q3uPePfIiaImcD8EcVD3jo4dcqTp-I"

# 搜索关键词 - 使用布尔运算符优化搜索
SEARCH_QUERY = 'inflation ("What is" OR "Explained" OR "what you need to know" OR "deep dive")'

# 过滤条件
LANGUAGE = 'en'  # 英文
DATE_AFTER = '2021-06-01T00:00:00Z'  # 2021年6月开始
DATE_BEFORE = '2024-02-29T23:59:59Z'  # 2024年2月结束

# 输出目录和文件名
OUTPUT_DIR = "youtube_results"
VIDEOS_CSV = os.path.join(OUTPUT_DIR, "videos.csv")
CHANNELS_CSV = os.path.join(OUTPUT_DIR, "channels.csv")

# 最多获取的结果数
MAX_RESULTS = 400  # 可以设置更大的值，因为只搜索一次


# ============================================================================
# 主程序
# ============================================================================

def search_videos(youtube, query, max_results=50, language='en', date_after=None, date_before=None):
    """搜索视频并返回video IDs"""
    print(f"\n🔍 搜索: '{query}'")
    print(f"   语言: {language}")
    if date_after:
        print(f"   时间范围: {date_after[:10]} 至 {date_before[:10] if date_before else '现在'}")

    video_ids = []
    next_page_token = None

    while len(video_ids) < max_results:
        try:
            search_params = {
                'q': query,
                'type': 'video',
                'part': 'id',
                'maxResults': min(50, max_results - len(video_ids)),
                'pageToken': next_page_token,
                'relevanceLanguage': language,
                'videoCaption': 'any'
            }

            # 添加时间过滤
            if date_after:
                search_params['publishedAfter'] = date_after
            if date_before:
                search_params['publishedBefore'] = date_before

            search_response = youtube.search().list(**search_params).execute()

            for item in search_response.get('items', []):
                video_ids.append(item['id']['videoId'])

            next_page_token = search_response.get('nextPageToken')

            if not next_page_token:
                break

            time.sleep(0.5)

        except HttpError as e:
            print(f"❌ API错误: {e}")
            break

    print(f"✅ 找到 {len(video_ids)} 个视频")
    return video_ids


def get_video_details(youtube, video_ids):
    """获取视频详细信息"""
    print(f"\n📊 获取 {len(video_ids)} 个视频的详细信息...")

    videos_data = []

    # YouTube API 一次最多查询50个视频
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]

        try:
            response = youtube.videos().list(
                part='id,snippet,contentDetails,statistics,recordingDetails',
                id=','.join(batch)
            ).execute()

            for item in response.get('items', []):
                video_data = {
                    'video_id': item['id'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'][:500],  # 限制长度
                    'published_at': item['snippet']['publishedAt'],
                    'recording_date': item.get('recordingDetails', {}).get('recordingDate', ''),
                    'duration': item['contentDetails']['duration'],
                    'definition': item['contentDetails']['definition'],
                    'caption': item['contentDetails']['caption'],
                    'tags': '|'.join(item['snippet'].get('tags', [])),
                    'default_language': item['snippet'].get('defaultLanguage', ''),
                    'default_audio_language': item['snippet'].get('defaultAudioLanguage', ''),
                    'category_id': item['snippet'].get('categoryId', ''),
                    'view_count': item['statistics'].get('viewCount', 0),
                    'like_count': item['statistics'].get('likeCount', 0),
                    'comment_count': item['statistics'].get('commentCount', 0),
                    'video_url': f"https://www.youtube.com/watch?v={item['id']}"
                }

                videos_data.append(video_data)

            print(f"  进度: {min(i + 50, len(video_ids))}/{len(video_ids)}")
            time.sleep(0.5)

        except HttpError as e:
            print(f"❌ 获取视频详情错误: {e}")

    print(f"✅ 成功获取 {len(videos_data)} 个视频的详细信息")
    return videos_data


def get_channel_details(youtube, channel_ids):
    """获取频道详细信息"""
    print(f"\n📺 获取频道信息...")

    channels_data = []
    unique_channel_ids = list(set(channel_ids))

    for i in range(0, len(unique_channel_ids), 50):
        batch = unique_channel_ids[i:i + 50]

        try:
            response = youtube.channels().list(
                part='id,snippet,contentDetails,statistics,brandingSettings',
                id=','.join(batch)
            ).execute()

            for item in response.get('items', []):
                channel_data = {
                    'channel_id': item['id'],
                    'channel_title': item['snippet']['title'],
                    'custom_url': item['snippet'].get('customUrl', ''),
                    'description': item['snippet']['description'][:500],  # 限制长度
                    'country': item['snippet'].get('country', ''),
                    'published_at': item['snippet']['publishedAt'],
                    'subscriber_count': item['statistics'].get('subscriberCount', 0),
                    'video_count': item['statistics'].get('videoCount', 0),
                    'view_count': item['statistics'].get('viewCount', 0),
                    'keywords': item.get('brandingSettings', {}).get('channel', {}).get('keywords', ''),
                    'channel_url': f"https://www.youtube.com/channel/{item['id']}"
                }

                channels_data.append(channel_data)

            print(f"  进度: {min(i + 50, len(unique_channel_ids))}/{len(unique_channel_ids)}")
            time.sleep(0.5)

        except HttpError as e:
            print(f"❌ 获取频道详情错误: {e}")

    print(f"✅ 成功获取 {len(channels_data)} 个频道的详细信息")
    return channels_data


def save_to_csv(data, filename, fieldnames):
    """保存数据到CSV文件"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"💾 已保存到: {filename}")


def main():
    print("=" * 70)
    print("YouTube 视频搜索 - 第一步：获取列表并导出CSV")
    print("=" * 70)
    print(f"\n📋 搜索配置:")
    print(f"   关键词: {SEARCH_QUERY}")
    print(f"   语言: English ({LANGUAGE})")
    print(f"   时间范围: {DATE_AFTER[:10]} 至 {DATE_BEFORE[:10]}")
    print(f"   最大结果数: {MAX_RESULTS}")

    # 检查API Key
    if YOUTUBE_API_KEY == "YOUR_NEW_API_KEY_HERE":
        print("\n❌ 错误: 请先替换代码中的 YOUTUBE_API_KEY")
        print("请用你的新API Key替换第16行的 YOUR_NEW_API_KEY_HERE")
        return

    # 初始化YouTube API客户端
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        print("✅ YouTube API 初始化成功")
    except Exception as e:
        print(f"❌ API 初始化失败: {e}")
        return

    # ========== 第一步：搜索视频 ==========
    # 使用单次布尔搜索（推荐）
    print(f"\n🔍 使用搜索查询: {SEARCH_QUERY}")
    video_ids = search_videos(
        youtube,
        SEARCH_QUERY,
        MAX_RESULTS,
        language=LANGUAGE,
        date_after=DATE_AFTER,
        date_before=DATE_BEFORE
    )

    # 如果想使用多次搜索，取消下面的注释并注释掉上面的代码
    # all_video_ids = []
    # for query in SEARCH_QUERIES:
    #     video_ids = search_videos(youtube, query, 50, LANGUAGE, DATE_AFTER, DATE_BEFORE)
    #     all_video_ids.extend(video_ids)
    # video_ids = list(set(all_video_ids))  # 去重

    print(f"\n📋 总共找到 {len(video_ids)} 个视频")

    # ========== 第二步：获取视频详细信息 ==========
    videos_data = get_video_details(youtube, video_ids)

    # ========== 第三步：获取频道信息 ==========
    channel_ids = [video['channel_id'] for video in videos_data]
    channels_data = get_channel_details(youtube, channel_ids)

    # ========== 第四步：保存为CSV ==========
    print("\n💾 保存数据到CSV...")

    # 保存视频数据
    video_fields = [
        'video_id', 'channel_id', 'channel_title', 'title', 'description',
        'published_at', 'recording_date', 'duration', 'definition', 'caption',
        'tags', 'default_language', 'default_audio_language', 'category_id',
        'view_count', 'like_count', 'comment_count', 'video_url'
    ]
    save_to_csv(videos_data, VIDEOS_CSV, video_fields)

    # 保存频道数据
    channel_fields = [
        'channel_id', 'channel_title', 'custom_url', 'description', 'country',
        'published_at', 'subscriber_count', 'video_count', 'view_count',
        'keywords', 'channel_url'
    ]
    save_to_csv(channels_data, CHANNELS_CSV, channel_fields)

    # ========== 完成 ==========
    print("\n" + "=" * 70)
    print("✅ 第一步完成!")
    print("=" * 70)
    print(f"\n📊 统计:")
    print(f"  - 视频数量: {len(videos_data)}")
    print(f"  - 频道数量: {len(channels_data)}")
    print(f"\n📁 输出文件:")
    print(f"  - 视频列表: {VIDEOS_CSV}")
    print(f"  - 频道列表: {CHANNELS_CSV}")
    print("\n💡 下一步: 使用这些video_id进行视频下载")


if __name__ == "__main__":
    main()