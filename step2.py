"""
YouTube视频下载 - 第二步测试版：使用yt-dlp获取所有维度信息
测试前10个视频
"""

import os
import csv
import json
import time
from datetime import datetime
import yt_dlp

# ============================================================================
# 配置部分
# ============================================================================

# 输入文件（第一步生成的CSV）
INPUT_CSV = "youtube_results/videos.csv"

# 输出目录
OUTPUT_DIR = "youtube_downloads_test"
METADATA_DIR = os.path.join(OUTPUT_DIR, "metadata")
TRANSCRIPTS_DIR = os.path.join(OUTPUT_DIR, "transcripts")
CHANNELS_DIR = os.path.join(OUTPUT_DIR, "channels")
VIDEOS_DIR = os.path.join(OUTPUT_DIR, "videos")  # 视频文件目录

# 测试：只下载前N个视频
TEST_LIMIT = 150

# 下载视频设置
DOWNLOAD_VIDEO = True  # 是否下载视频文件
VIDEO_QUALITY = 'best'  # 视频质量：'best' (最高质量) 或 '1080p', '720p' 等

# ============================================================================
# 辅助函数
# ============================================================================

def read_video_ids_from_csv(csv_file, limit=None):
    """从CSV文件读取video_id列表"""
    video_ids = []

    if not os.path.exists(csv_file):
        print(f"❌ 找不到文件: {csv_file}")
        print("请先运行第一步代码生成videos.csv")
        return []

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_ids.append(row['video_id'])
            if limit and len(video_ids) >= limit:
                break

    return video_ids


def clean_info_for_json(info):
    """
    清理 yt-dlp 返回的 info 对象，移除不可序列化的对象
    能序列化的都保留，不能序列化的就跳过
    """
    if info is None:
        return None

    # 如果不是字典、列表等复杂类型，直接测试能否序列化
    if not isinstance(info, (dict, list, tuple)):
        try:
            json.dumps(info)
            return info
        except (TypeError, ValueError):
            return None  # 不能序列化就返回 None

    # 处理字典
    if isinstance(info, dict):
        cleaned = {}
        for key, value in info.items():
            try:
                # 递归清理值
                cleaned_value = clean_info_for_json(value)

                # 如果清理后的值不是 None，就保存
                if cleaned_value is not None:
                    cleaned[key] = cleaned_value
                # 特殊处理：如果原值就是 None，也要保留
                elif value is None:
                    cleaned[key] = None

            except Exception as e:
                # 任何异常都跳过这个字段
                print(f"    ⚠️  跳过字段 '{key}': {type(value).__name__}")
                continue

        return cleaned

    # 处理列表或元组
    if isinstance(info, (list, tuple)):
        cleaned_list = []
        for item in info:
            try:
                cleaned_item = clean_info_for_json(item)
                if cleaned_item is not None or item is None:
                    cleaned_list.append(cleaned_item)
            except Exception:
                # 跳过不能序列化的列表项
                continue

        return cleaned_list if isinstance(info, list) else tuple(cleaned_list)

    # 其他类型尝试直接序列化
    try:
        json.dumps(info)
        return info
    except (TypeError, ValueError):
        return None


def extract_channel_info(info):
    """从yt-dlp返回的info中提取频道信息"""
    channel_data = {
        # IDs & metadata
        'channel_id': info.get('channel_id'),
        'custom_url': info.get('channel_url', '').replace('https://www.youtube.com/channel/', '').replace('https://www.youtube.com/', ''),
        'channel_handle': info.get('uploader_id'),  # @handle
        'title': info.get('channel'),
        'uploader': info.get('uploader'),

        # Description需要从完整频道页面获取，这里先留空
        'description': '',
        'country': '',

        # Ownership/affiliation signals
        'channel_follower_count': info.get('channel_follower_count'),

        # Links - yt-dlp可能不直接提供，需要额外抓取
        'external_links': [],
        'business_email': '',
    }

    return channel_data


def extract_video_info(info):
    """从yt-dlp返回的info中提取视频信息"""
    video_data = {
        # IDs & timestamps
        'video_id': info.get('id'),
        'channel_id': info.get('channel_id'),
        'published_at': info.get('upload_date'),  # YYYYMMDD格式
        'timestamp': info.get('timestamp'),  # Unix timestamp
        'release_timestamp': info.get('release_timestamp'),

        # Textual metadata
        'title': info.get('title'),
        'description': info.get('description'),
        'tags': info.get('tags', []),
        'categories': info.get('categories', []),
        'default_language': info.get('language'),

        # Duration/format
        'duration': info.get('duration'),  # 秒数
        'duration_string': info.get('duration_string'),
        'definition': 'hd' if info.get('height', 0) >= 720 else 'sd',
        'resolution': info.get('resolution'),
        'width': info.get('width'),
        'height': info.get('height'),
        'fps': info.get('fps'),
        'vcodec': info.get('vcodec'),
        'acodec': info.get('acodec'),
        'filesize': info.get('filesize'),  # 文件大小（字节）
        'filesize_approx': info.get('filesize_approx'),

        # Captions
        'has_subtitles': bool(info.get('subtitles')),
        'has_automatic_captions': bool(info.get('automatic_captions')),
        'available_subtitles': list(info.get('subtitles', {}).keys()),
        'available_auto_captions': list(info.get('automatic_captions', {}).keys()),

        # Content rating
        'age_limit': info.get('age_limit'),
        'is_live': info.get('is_live'),
        'was_live': info.get('was_live'),

        # Statistics
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'comment_count': info.get('comment_count'),

        # Additional
        'thumbnail': info.get('thumbnail'),
        'webpage_url': info.get('webpage_url'),
        'channel_url': info.get('channel_url'),
    }

    return video_data


def extract_transcript_info(subtitles_data, video_id):
    """提取字幕信息（带时间戳）"""
    transcripts = []

    if not subtitles_data:
        return transcripts

    # 检查两个可能的目录
    search_dirs = [TRANSCRIPTS_DIR, VIDEOS_DIR]
    subtitle_files = []

    for search_dir in search_dirs:
        video_dir = os.path.join(search_dir, video_id)
        if os.path.exists(video_dir):
            subtitle_files = [
                os.path.join(video_dir, f)
                for f in os.listdir(video_dir)
                if f.startswith(video_id) and f.endswith('.json3')
            ]
            if subtitle_files:
                break

    for subtitle_file in subtitle_files:
        try:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # JSON3格式包含完整的时间戳信息
                if 'events' in data:
                    segments = []
                    for event in data['events']:
                        if 'segs' in event:
                            text = ''.join([seg.get('utf8', '') for seg in event['segs']])
                            segments.append({
                                'start_ms': event.get('tStartMs', 0),
                                'end_ms': event.get('tStartMs', 0) + event.get('dDurationMs', 0),
                                'text': text.strip()
                            })

                    lang = os.path.basename(subtitle_file).split('.')[-2]
                    transcripts.append({
                        'language': lang,
                        'segments': segments
                    })
        except Exception as e:
            print(f"  ⚠️  解析字幕文件失败 {os.path.basename(subtitle_file)}: {e}")

    return transcripts

    return transcripts


def download_video_metadata(video_id, output_dir, download_video=True, video_quality='best'):
    """
    使用yt-dlp下载单个视频的所有元数据和视频文件

    Args:
        video_id: 视频ID
        output_dir: 输出目录
        download_video: 是否下载视频文件
        video_quality: 视频质量 ('best', '1080p', '720p', etc.)
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    # 创建视频专属目录
    video_dir = os.path.join(output_dir, video_id)
    os.makedirs(video_dir, exist_ok=True)

    # 基础配置
    ydl_opts = {
        # 输出路径 - 只设置 outtmpl，不设置 paths
        'outtmpl': os.path.join(video_dir, '%(id)s.%(ext)s'),

        # 保存完整的JSON信息
        'writeinfojson': True,
        'clean_infojson': False,

        # 下载字幕（所有可用语言）
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB'],
        'subtitlesformat': 'json3',

        # 下载其他元数据
        'writethumbnail': True,
        'writedescription': True,

        # 获取完整信息
        'extract_flat': False,
        'forcejson': True,

        # 输出控制
        'quiet': False,
        'no_warnings': False,
    }

    # 如果下载视频，配置视频格式
    if download_video:
        # 格式选择：优先下载最高质量的MP4格式
        # bestvideo[ext=mp4]+bestaudio[ext=m4a] = 最高质量的MP4视频+音频
        # best[ext=mp4] = 如果上面的格式不可用，下载最好的MP4
        # best = 最后的fallback，下载任何格式的最高质量
        format_string = 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/bestvideo+bestaudio/best'

        if video_quality == '720p':
            format_string = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best'
        elif video_quality == '480p':
            format_string = 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]/best'
        elif video_quality == 'best':
            format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best'

        ydl_opts.update({
            'format': format_string,
            'merge_output_format': 'mp4',  # 合并为MP4格式
        })
        print(f"  📹 下载视频: {video_quality}")
    else:
        ydl_opts['skip_download'] = True
        print(f"  📄 仅下载元数据（不下载视频）")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"  📥 处理: {video_id}")
            info = ydl.extract_info(url, download=True)

            return info

    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return None


def process_videos(video_ids, download_video=True, video_quality='best'):
    """批量处理视频"""
    print(f"\n🚀 开始处理 {len(video_ids)} 个视频")
    if download_video:
        print(f"   视频质量: {video_quality}")
        print(f"   ⚠️  下载视频需要较长时间和存储空间")

    os.makedirs(METADATA_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    os.makedirs(CHANNELS_DIR, exist_ok=True)
    if download_video:
        os.makedirs(VIDEOS_DIR, exist_ok=True)

    all_videos = []
    all_channels = {}
    all_transcripts = []

    for i, video_id in enumerate(video_ids, 1):
        print(f"\n[{i}/{len(video_ids)}] 处理视频: {video_id}")

        # 下载元数据和视频
        output_location = VIDEOS_DIR if download_video else TRANSCRIPTS_DIR
        info = download_video_metadata(video_id, output_location, download_video, video_quality)

        if info:
            # 提取视频信息
            video_data = extract_video_info(info)
            all_videos.append(video_data)

            # 提取频道信息
            channel_id = info.get('channel_id')
            if channel_id and channel_id not in all_channels:
                channel_data = extract_channel_info(info)
                all_channels[channel_id] = channel_data

            # 提取字幕信息
            transcript_data = extract_transcript_info(
                info.get('subtitles') or info.get('automatic_captions'),
                video_id
            )

            if transcript_data:
                all_transcripts.append({
                    'video_id': video_id,
                    'transcripts': transcript_data
                })

            # 保存完整的JSON信息（清理后）
            json_path = os.path.join(METADATA_DIR, f"{video_id}_full.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                cleaned_info = clean_info_for_json(info)
                json.dump(cleaned_info, f, ensure_ascii=False, indent=2)

        # 避免请求过快
        time.sleep(2 if download_video else 1)

    return all_videos, all_channels, all_transcripts


def save_results(videos, channels, transcripts):
    """保存处理结果为CSV和JSON"""

    # 1. 保存视频信息为CSV
    if videos:
        csv_path = os.path.join(OUTPUT_DIR, "videos_detailed.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=videos[0].keys())
            writer.writeheader()
            writer.writerows(videos)
        print(f"\n💾 视频信息已保存: {csv_path}")

    # 2. 保存频道信息为CSV
    if channels:
        csv_path = os.path.join(OUTPUT_DIR, "channels_detailed.csv")
        channel_list = list(channels.values())
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=channel_list[0].keys())
            writer.writeheader()
            writer.writerows(channel_list)
        print(f"💾 频道信息已保存: {csv_path}")

    # 3. 保存字幕信息为JSON（CSV不适合存储层级数据）
    if transcripts:
        json_path = os.path.join(OUTPUT_DIR, "transcripts_all.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(transcripts, f, ensure_ascii=False, indent=2)
        print(f"💾 字幕信息已保存: {json_path}")

    # 4. 计算视频文件总大小
    total_size_mb = 0
    if DOWNLOAD_VIDEO and os.path.exists(VIDEOS_DIR):
        for root, dirs, files in os.walk(VIDEOS_DIR):
            for file in files:
                if file.endswith('.mp4'):
                    filepath = os.path.join(root, file)
                    total_size_mb += os.path.getsize(filepath) / (1024 * 1024)

    # 5. 生成摘要报告
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_videos': len(videos),
        'total_channels': len(channels),
        'videos_with_transcripts': len(transcripts),
        'downloaded_videos': DOWNLOAD_VIDEO,
        'video_quality': VIDEO_QUALITY if DOWNLOAD_VIDEO else 'N/A',
        'total_video_size_mb': round(total_size_mb, 2) if DOWNLOAD_VIDEO else 0,
        'statistics': {
            'videos_with_subtitles': sum(1 for v in videos if v['has_subtitles']),
            'videos_with_auto_captions': sum(1 for v in videos if v['has_automatic_captions']),
            'total_views': sum(v['view_count'] or 0 for v in videos),
            'total_likes': sum(v['like_count'] or 0 for v in videos),
            'total_duration_seconds': sum(v['duration'] or 0 for v in videos),
        }
    }

    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"💾 摘要报告已保存: {summary_path}")

    if DOWNLOAD_VIDEO and total_size_mb > 0:
        print(f"\n📦 视频文件总大小: {total_size_mb:.2f} MB ({total_size_mb/1024:.2f} GB)")


def main():
    print("=" * 70)
    print("YouTube 下载测试 - 第二步：使用yt-dlp获取所有维度")
    print("=" * 70)
    print(f"\n⚙️  配置:")
    print(f"   输入文件: {INPUT_CSV}")
    print(f"   输出目录: {OUTPUT_DIR}")
    print(f"   测试数量: 前 {TEST_LIMIT} 个视频")
    print(f"   下载视频: {'是' if DOWNLOAD_VIDEO else '否（仅元数据）'}")
    if DOWNLOAD_VIDEO:
        print(f"   视频质量: {VIDEO_QUALITY}")
        print(f"\n   ⚠️  下载10个高清视频预计需要:")
        print(f"      - 时间: 10-30分钟（取决于网速和视频长度）")
        print(f"      - 空间: 1-5 GB（取决于视频质量和长度）")

    # 1. 读取video_id列表
    print("\n📖 读取视频列表...")
    video_ids = read_video_ids_from_csv(INPUT_CSV, limit=TEST_LIMIT)

    if not video_ids:
        print("❌ 没有找到视频ID，程序退出")
        return

    print(f"✅ 读取到 {len(video_ids)} 个视频ID")

    # 2. 处理视频
    videos, channels, transcripts = process_videos(video_ids, DOWNLOAD_VIDEO, VIDEO_QUALITY)

    # 3. 保存结果
    print("\n" + "=" * 70)
    print("保存结果")
    print("=" * 70)
    save_results(videos, channels, transcripts)

    # 4. 打印统计
    print("\n" + "=" * 70)
    print("✅ 测试完成!")
    print("=" * 70)
    print(f"\n📊 统计:")
    print(f"   成功处理: {len(videos)}/{len(video_ids)} 个视频")
    print(f"   涉及频道: {len(channels)} 个")
    print(f"   有字幕的: {len(transcripts)} 个")

    print(f"\n📁 输出文件:")
    print(f"   - 视频详情: {OUTPUT_DIR}/videos_detailed.csv")
    print(f"   - 频道详情: {OUTPUT_DIR}/channels_detailed.csv")
    print(f"   - 字幕数据: {OUTPUT_DIR}/transcripts_all.json")
    print(f"   - 摘要报告: {OUTPUT_DIR}/summary.json")
    print(f"   - 完整JSON: {METADATA_DIR}/[video_id]_full.json")
    if DOWNLOAD_VIDEO:
        print(f"   - 视频文件: {VIDEOS_DIR}/[video_id]/[video_id].mp4")
        print(f"   - 字幕文件: {VIDEOS_DIR}/[video_id]/[video_id].en.json3")
    else:
        print(f"   - 字幕文件: {TRANSCRIPTS_DIR}/[video_id]/*.json3")

    print("\n💡 提示:")
    print("   1. 检查输出文件，确认数据完整性")
    print("   2. 如果满意，可以修改 TEST_LIMIT 处理更多视频")
    if DOWNLOAD_VIDEO:
        print("   3. 如果只需要元数据，可以设置 DOWNLOAD_VIDEO = False")
        print("   4. 可以调整 VIDEO_QUALITY 为 '720p' 或 '480p' 节省空间")
    else:
        print("   3. 如果需要下载视频，可以设置 DOWNLOAD_VIDEO = True")


if __name__ == "__main__":
    main()