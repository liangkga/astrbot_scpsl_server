from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import socket
import struct
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
import re
import sqlite3
import os
from datetime import datetime

@register("scpsl_server_query", "若梦", "SCP:SL服务器查询插件，仿照server_Qchat功能", "1.0.0")
class SCPSLServerQuery(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.default_port = 7777
        self.timeout = 5
        self.db_path = os.path.join(os.path.dirname(__file__), 'group_servers.db')
        # 管理员OpenID列表
        self.admin_openids = set()
        self._init_database()
        self._init_admin_system()
        
        # 添加指定的管理员OpenID
        self._ensure_admin_exists("o_2Tqls-aOEGHVOqZVz6M2kZWtmrpU", "系统管理员")
        
    @filter.command("cx")
    async def query_server_status(self, event: AstrMessageEvent):
        """查询SCP:SL服务器在线人数和状态"""
        message_parts = event.message_str.strip().split()
        
        if len(message_parts) < 2:
            yield event.plain_result("请提供服务器IP地址！\n使用方法: /cx <服务器IP> [端口]\n例如: /cx 127.0.0.1 7777")
            return
            
        server_ip = message_parts[1]
        
        # 解析端口参数，添加错误处理
        if len(message_parts) > 2:
            try:
                # 清理端口参数，移除可能的方括号或其他字符
                port_str = message_parts[2].strip('[]')
                server_port = int(port_str)
                if not (1 <= server_port <= 65535):
                    yield event.plain_result("❌ 端口号必须在1-65535之间！")
                    return
            except ValueError:
                yield event.plain_result(f"❌ 无效的端口号: {message_parts[2]}\n端口号必须是数字！")
                return
        else:
            server_port = self.default_port
        
        try:
            server_info = await self.query_scpsl_server(server_ip, server_port)
            if server_info:
                response = f"🎮 SCP:SL 服务器状态\n"
                response += f"📍 服务器: {server_ip}:{server_port}\n"
                response += f"👥 在线人数: {server_info.get('players', 'N/A')}/{server_info.get('max_players', 'N/A')}\n"
                response += f"🏷️ 服务器名: {server_info.get('name', 'Unknown')}\n"
                response += f"🎯 游戏模式: {server_info.get('gamemode', 'Unknown')}\n"
                response += f"🗺️ 地图: {server_info.get('map', 'Unknown')}\n"
                response += f"⏱️ 回合时间: {server_info.get('round_time', 'N/A')}\n"
                response += f"🔄 状态: {'🟢 在线' if server_info.get('online') else '🔴 离线'}"
                yield event.plain_result(response)
            else:
                yield event.plain_result(f"❌ 无法连接到服务器 {server_ip}:{server_port}\n请检查IP地址和端口是否正确！")
        except Exception as e:
            logger.error(f"查询服务器时出错: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    

    
    @filter.command("servers")
    async def list_servers(self, event: AstrMessageEvent):
        """显示预设服务器列表"""
        server_list = """🎮 SCP:SL 服务器列表

🌸 椿雨服务器:
• 椿雨纯净服#1: 43.139.108.159:8000
• 椿雨纯净服#2: 43.139.108.159:8001
• 椿雨插件服#1: 43.139.108.159:8002
• 椿雨插件服#2: 43.139.108.159:8003
• 椿雨萌新服: 43.139.108.159:7777

📝 使用方法:
• /xy - 查询所有椿雨服务器状态
• /cx <IP:端口> - 查询自定义服务器"""
        yield event.plain_result(server_list)
    
    @filter.command("xy")
    async def query_chunyu_servers(self, event: AstrMessageEvent):
        """查询所有椿雨服务器状态"""
        servers = [
            ("43.139.108.159",8000, "椿雨纯净服#1"),
            ("43.139.108.159",8001, "椿雨纯净服#2"),
            ("43.139.108.159",8002, "椿雨插件服#1"),
            ("43.139.108.159",8003, "椿雨插件服#2"),
            ("43.139.108.159",7777, "椿雨萌新服"),
            ("8.138.236.97", 5000, "银狼服务器")
        ]
        
        response = "服务器状态总览\n"
        online_count = 0
        total_players = 0
        
        for ip, port, name in servers:
            try:
                server_info = await self.query_scpsl_server(ip, port)
                if server_info and server_info.get('status') != 'offline':
                    online_count += 1
                    players = server_info.get('players', 0)
                    max_players = server_info.get('max_players', 0)
                    total_players += players if isinstance(players, int) else 0
                    
                    response += f"{name} [{players}/{max_players}]\n"
                else:
                    response += f"{name} [离线]\n"
            except Exception as e:
                logger.error(f"查询{name}时出错: {e}")
                response += f"{name} [查询失败]\n"
        
        response += f"总计: {online_count}/{len(servers)} 台服务器在线\n"
        response += f"总在线人数: {total_players} 人"
        
        yield event.plain_result(response)
    
    async def _query_preset_server(self, event: AstrMessageEvent, ip: str, port: int, server_name: str):
        """查询预设服务器的通用方法"""
        try:
            server_info = await self.query_scpsl_server(ip, port)
            if server_info:
                response = f"🎮 {server_name} 状态\n"
                response += f"📍 服务器: {ip}:{port}\n"
                response += f"👥 在线人数: {server_info.get('players', 'N/A')}/{server_info.get('max_players', 'N/A')}\n"
                response += f"🏷️ 服务器名: {server_info.get('name', 'Unknown')}\n"
                response += f"🎯 游戏模式: {server_info.get('gamemode', 'Unknown')}\n"
                response += f"🗺️ 地图: {server_info.get('map', 'Unknown')}\n"
                response += f"⏱️ 回合时间: {server_info.get('round_time', 'N/A')}\n"
                response += f"🌐 延迟: {server_info.get('ping', 'N/A')}ms\n"
                response += f"🔄 状态: {'🟢 在线' if server_info.get('online') else '🔴 离线'}"
                yield event.plain_result(response)
            else:
                yield event.plain_result(f"❌ 无法连接到 {server_name} ({ip}:{port})\n请检查服务器是否在线！")
        except Exception as e:
            logger.error(f"查询{server_name}时出错: {e}")
            yield event.plain_result(f"❌ 查询{server_name}失败: {str(e)}")
    
    @filter.regex(r".*炸了\?.*|.*服务器炸了\?.*")
    async def auto_check_server(self, event: AstrMessageEvent):
        """自动检测包含'炸了?'的消息并返回服务器状态"""
        # 检查所有椿雨服务器的状态
        servers = [
            ("43.139.108.159", 8000, "椿雨纯净服#1"),
            ("43.139.108.159", 8001, "椿雨纯净服#2"),
            ("43.139.108.159", 8002, "椿雨插件服#1"),
            ("43.139.108.159", 8003, "椿雨插件服#2"),
            ("43.139.108.159", 7777, "椿雨萌新服")
        ]
        
        response = "🤖 自动检测椿雨服务器状态\n\n"
        online_count = 0
        
        for ip, port, name in servers:
            try:
                server_info = await self.query_scpsl_server(ip, port)
                if server_info and server_info.get('online'):
                    status = "🟢 在线"
                    players = f"{server_info.get('players', 'N/A')}/{server_info.get('max_players', 'N/A')}"
                    ping = f"{server_info.get('ping', 'N/A')}ms"
                    online_count += 1
                else:
                    status = "🔴 离线"
                    players = "N/A"
                    ping = "N/A"
                
                response += f"• {name}: {status} | 👥{players} | 🌐{ping}\n"
            except:
                response += f"• {name}: 🔴 离线 | 👥N/A | 🌐N/A\n"
        
        response += f"\n📊 总计: {online_count}/5 个椿雨服务器在线"
        yield event.plain_result(response)
    
    async def _query_server_tcp(self, ip: str, port: int) -> Dict[str, Any]:
        """使用支持challenge的A2S协议查询服务器信息"""
        # 尝试多个可能的查询端口
        query_ports = [port, port + 1, port - 1]
        
        for query_port in query_ports:
            sock = None
            try:
                # 创建UDP socket进行A2S查询
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5.0)  # 增加超时时间以适应challenge机制
                
                start_time = time.time()
                
                # 第一次A2S_INFO查询
                query = b"\xFF\xFF\xFF\xFF\x54Source Engine Query\x00"
                sock.sendto(query, (ip, query_port))
                
                response, addr = sock.recvfrom(1400)
                
                if len(response) < 5:
                    continue
                
                # 检查响应头
                if response[:4] != b"\xFF\xFF\xFF\xFF":
                    continue
                
                # 检查是否收到challenge响应
                if response[4] == 0x41:  # S2C_CHALLENGE
                    if len(response) >= 9:
                        # 提取challenge值
                        challenge = struct.unpack('<I', response[5:9])[0]
                        
                        # 重新发送带challenge的查询
                        query_with_challenge = query + struct.pack('<I', challenge)
                        sock.sendto(query_with_challenge, (ip, query_port))
                        response, addr = sock.recvfrom(1400)
                    else:
                        # challenge响应格式错误
                        continue
                
                ping = round((time.time() - start_time) * 1000)
                
                # 解析A2S_INFO响应
                if len(response) >= 5 and response[4] == 0x49:  # A2S_INFO response
                    result = self._parse_a2s_info(response[5:], ping)
                    if result.get('status') == 'online':
                        return result
                
            except socket.timeout:
                logger.debug(f"查询超时: {ip}:{query_port}")
                continue
            except ConnectionRefusedError:
                logger.debug(f"连接被拒绝: {ip}:{query_port}")
                continue
            except Exception as e:
                logger.debug(f"查询异常 {ip}:{query_port}: {str(e)}")
                continue
            finally:
                # 确保socket被正确关闭
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
        
        # 如果所有端口都失败，返回错误
        return {'status': 'offline', 'error': '无法连接到服务器'}
    
    def _parse_a2s_info(self, data: bytes, ping: int) -> Dict[str, Any]:
         """解析A2S_INFO响应数据"""
         try:
             offset = 0
             
             # 协议版本
             protocol = data[offset]
             offset += 1
             
             # 服务器名称
             server_name_end = data.find(b'\x00', offset)
             server_name = data[offset:server_name_end].decode('utf-8', errors='ignore')
             offset = server_name_end + 1
             
             # 地图名称
             map_name_end = data.find(b'\x00', offset)
             map_name = data[offset:map_name_end].decode('utf-8', errors='ignore')
             offset = map_name_end + 1
             
             # 文件夹名称
             folder_end = data.find(b'\x00', offset)
             folder = data[offset:folder_end].decode('utf-8', errors='ignore')
             offset = folder_end + 1
             
             # 游戏名称
             game_end = data.find(b'\x00', offset)
             game = data[offset:game_end].decode('utf-8', errors='ignore')
             offset = game_end + 1
             
             # 应用ID
             if offset + 2 <= len(data):
                 app_id = struct.unpack('<H', data[offset:offset+2])[0]
                 offset += 2
             else:
                 app_id = 0
             
             # 玩家数量
             if offset < len(data):
                 players = data[offset]
                 offset += 1
             else:
                 players = 0
             
             # 最大玩家数
             if offset < len(data):
                 max_players = data[offset]
                 offset += 1
             else:
                 max_players = 20
             
             # 机器人数量
             if offset < len(data):
                 bots = data[offset]
                 offset += 1
             else:
                 bots = 0
             
             # 服务器类型
             if offset < len(data):
                 server_type = chr(data[offset])
                 offset += 1
             else:
                 server_type = 'd'
             
             # 平台
             if offset < len(data):
                 platform = chr(data[offset])
                 offset += 1
             else:
                 platform = 'l'
             
             # 是否需要密码
             if offset < len(data):
                 password = bool(data[offset])
                 offset += 1
             else:
                 password = False
             
             # VAC状态
             if offset < len(data):
                 vac = bool(data[offset])
                 offset += 1
             else:
                 vac = False
             
             return {
                 'status': 'online',
                 'players': players,
                 'max_players': max_players,
                 'server_name': server_name,
                 'map': map_name,
                 'game_mode': game if game else '未知模式',
                 'round_time': '未知',
                 'ping': ping,
                 'bots': bots,
                 'password': password,
                 'vac': vac
             }
             
         except Exception as e:
             return {
                 'status': 'error',
                 'error': f'解析A2S响应失败: {str(e)}'
             }
     
    async def query_scpsl_server(self, ip: str, port: int) -> dict:
        """查询SCP:SL服务器信息（使用A2S协议）"""
        # 直接使用A2S协议查询
        result = await self._query_server_tcp(ip, port)
        
        if result and result.get('status') == 'online':
            # 转换为兼容格式
            return {
                'online': True,
                'ping': result.get('ping', 0),
                'players': result.get('players', 0),
                'max_players': result.get('max_players', 20),
                'name': result.get('server_name', 'SCP:SL Server'),
                'gamemode': result.get('game_mode', 'Classic'),
                'map': result.get('map', 'Facility'),
                'round_time': result.get('round_time', '00:00'),
                'version': 'Unknown'
            }
        else:
            return None
    
    async def query_scpsl_server_udp(self, ip: str, port: int) -> dict:
        """UDP查询服务器信息（使用A2S协议）"""
        # 直接调用TCP方法，因为它实际上使用的是UDP A2S协议
        return await self._query_server_tcp(ip, port)
    
    def _init_database(self):
        """初始化数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_servers (
                    group_id TEXT PRIMARY KEY,
                    server_ip TEXT NOT NULL,
                    server_port INTEGER DEFAULT 7777,
                    server_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_users (
                    openid TEXT PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
    
    def _init_admin_system(self):
        """初始化管理员系统"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT openid FROM admin_users')
            results = cursor.fetchall()
            self.admin_openids = {row[0] for row in results}
            conn.close()
            logger.info(f"已加载 {len(self.admin_openids)} 个管理员")
        except Exception as e:
            logger.error(f"管理员系统初始化失败: {e}")
    
    def _is_admin(self, openid: str) -> bool:
        """检查用户是否为管理员"""
        return openid in self.admin_openids
    
    def _get_user_openid(self, event) -> Optional[str]:
        """获取用户OpenID"""
        # 优先获取用户ID，而不是群聊ID
        user_id = getattr(event, 'user_id', None) or getattr(event, 'sender_id', None)
        if user_id:
            return str(user_id)
        
        # 如果是私聊，则使用session_id
        session_id = getattr(event, 'session_id', None)
        if session_id and session_id != 'private':
            return str(session_id)
        
        return None
    
    def _add_admin(self, openid: str, username: str = None, created_by: str = None) -> bool:
        """添加管理员"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO admin_users (openid, username, created_by)
                VALUES (?, ?, ?)
            ''', (openid, username, created_by))
            conn.commit()
            conn.close()
            self.admin_openids.add(openid)
            return True
        except Exception as e:
            logger.error(f"添加管理员失败: {e}")
            return False
    
    def _remove_admin(self, openid: str) -> bool:
        """移除管理员"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admin_users WHERE openid = ?', (openid,))
            conn.commit()
            conn.close()
            
            # 从内存中移除
            self.admin_openids.discard(openid)
            return True
        except Exception as e:
            logger.error(f"移除管理员失败: {e}")
            return False
    
    def _ensure_admin_exists(self, openid: str, username: str = "系统管理员"):
        """确保指定的管理员存在于数据库中"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute('SELECT openid FROM admin_users WHERE openid = ?', (openid,))
            if cursor.fetchone():
                conn.close()
                return
            
            # 添加到数据库
            cursor.execute(
                'INSERT INTO admin_users (openid, username, created_at, created_by) VALUES (?, ?, ?, ?)',
                (openid, username, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system')
            )
            conn.commit()
            conn.close()
            
            # 添加到内存
            self.admin_openids.add(openid)
            logger.info(f"系统管理员已添加: {openid}")
            
        except Exception as e:
            logger.error(f"添加系统管理员失败: {e}")
    
    def _get_group_server(self, group_id: str) -> Optional[Tuple[str, int, str]]:
        """获取群聊绑定的服务器信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT server_ip, server_port, server_name FROM group_servers WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"查询群聊服务器失败: {e}")
            return None
    
    def _set_group_server(self, group_id: str, server_ip: str, server_port: int = 7777, server_name: str = None) -> bool:
        """设置群聊绑定的服务器"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO group_servers 
                (group_id, server_ip, server_port, server_name, updated_at) 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, server_ip, server_port, server_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"设置群聊服务器失败: {e}")
            return False
    
    @filter.command("openid")
    async def get_group_openid(self, event: AstrMessageEvent):
        """获取当前群聊的openid"""
        # 获取群号/openid
        group_id = getattr(event, 'group_id', None) or getattr(event, 'session_id', 'private')
        if not group_id or group_id == 'private':
            yield event.plain_result("❌ 此命令只能在群聊中使用！")
            return
        
        group_id = str(group_id)
        
        # 显示当前群聊的openid信息
        response = f"📋 当前群聊信息\n"
        response += f"🆔 群聊OpenID: {group_id}\n"
        response += f"💡 此OpenID用于区分不同的群聊"
        
        yield event.plain_result(response)
    
    @filter.command("myid")
    async def get_user_openid(self, event: AstrMessageEvent):
        """获取当前用户的OpenID"""
        user_openid = self._get_user_openid(event)
        
        if not user_openid:
            yield event.plain_result("❌ 无法获取用户OpenID！")
            return
        
        # 获取群聊信息（如果在群聊中）
        group_id = getattr(event, 'group_id', None)
        
        response = f"👤 用户信息\n"
        response += f"🆔 用户OpenID: {user_openid}\n"
        
        if group_id:
            response += f"📱 当前群聊: {group_id}\n"
        
        # 检查管理员权限
        is_admin = self._is_admin(user_openid)
        if is_admin:
            response += f"👑 管理员权限: 是\n"
        else:
            response += f"👤 管理员权限: 否\n"
        
        response += f"💡 用户OpenID用于身份识别和权限管理"
        
        yield event.plain_result(response)
    
    @filter.command("groups")
    async def list_all_groups(self, event: AstrMessageEvent):
        """列出所有已绑定服务器的群聊"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT group_id, server_ip, server_port, server_name, created_at FROM group_servers ORDER BY created_at DESC')
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                yield event.plain_result("📋 暂无群聊绑定服务器")
                return
            
            response = "📋 已绑定服务器的群聊列表\n\n"
            for i, (gid, ip, port, name, created_at) in enumerate(results, 1):
                response += f"{i}. 群聊ID: {gid}\n"
                response += f"   服务器: {name or f'{ip}:{port}'}\n"
                response += f"   地址: {ip}:{port}\n"
                response += f"   绑定时间: {created_at[:19]}\n\n"
            
            yield event.plain_result(response)
        except Exception as e:
            logger.error(f"查询群聊列表失败: {e}")
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    @filter.command("unbind")
    async def unbind_group_server(self, event: AstrMessageEvent):
        """解绑当前群聊的服务器或删除指定群聊的绑定"""
        message_parts = event.message_str.strip().split()
        
        # 获取当前群号和用户OpenID
        current_group_id = getattr(event, 'group_id', None) or getattr(event, 'session_id', 'private')
        user_openid = self._get_user_openid(event)
        
        if not current_group_id or current_group_id == 'private':
            yield event.plain_result("❌ 此命令只能在群聊中使用！")
            return
        
        current_group_id = str(current_group_id)
        is_admin = self._is_admin(user_openid) if user_openid else False
        
        # 如果只有/unbind命令，解绑当前群聊
        if len(message_parts) == 1:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT server_name, server_ip, server_port FROM group_servers WHERE group_id = ?', (current_group_id,))
                result = cursor.fetchone()
                
                if not result:
                    yield event.plain_result(f"❌ 当前群聊(OpenID: {current_group_id})没有绑定服务器！")
                    conn.close()
                    return
                
                server_name, server_ip, server_port = result
                cursor.execute('DELETE FROM group_servers WHERE group_id = ?', (current_group_id,))
                conn.commit()
                conn.close()
                
                response = f"✅ 成功解绑当前群聊的服务器！\n"
                response += f"🆔 群聊OpenID: {current_group_id}\n"
                response += f"🏷️ 已解绑服务器: {server_name or f'{server_ip}:{server_port}'}"
                yield event.plain_result(response)
                
            except Exception as e:
                logger.error(f"解绑群聊服务器失败: {e}")
                yield event.plain_result(f"❌ 解绑失败: {str(e)}")
            return
        
        # 如果指定了群聊ID，删除指定群聊的绑定（需要管理员权限）
        target_group_id = message_parts[1]
        
        # 检查权限：只有管理员才能删除其他群聊的绑定
        if target_group_id != current_group_id and not is_admin:
            yield event.plain_result("❌ 只有管理员才能删除其他群聊的服务器绑定！\n💡 使用 /unbind 解绑当前群聊的服务器")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT server_name, server_ip, server_port FROM group_servers WHERE group_id = ?', (target_group_id,))
            result = cursor.fetchone()
            
            if not result:
                yield event.plain_result(f"❌ 群聊(OpenID: {target_group_id})没有绑定服务器！")
                conn.close()
                return
            
            server_name, server_ip, server_port = result
            cursor.execute('DELETE FROM group_servers WHERE group_id = ?', (target_group_id,))
            conn.commit()
            conn.close()
            
            if target_group_id == current_group_id:
                response = f"✅ 成功解绑当前群聊的服务器！\n"
                response += f"🆔 群聊OpenID: {current_group_id}\n"
                response += f"🏷️ 已解绑服务器: {server_name or f'{server_ip}:{server_port}'}"
            else:
                response = f"✅ 管理员操作：成功删除指定群聊的服务器绑定！\n"
                response += f"🆔 目标群聊OpenID: {target_group_id}\n"
                response += f"🏷️ 已删除服务器: {server_name or f'{server_ip}:{server_port}'}\n"
                response += f"👑 管理员OpenID: {user_openid}\n"
                response += f"🔧 操作群聊: {current_group_id}"
            
            yield event.plain_result(response)
            
        except Exception as e:
            logger.error(f"删除群聊绑定失败: {e}")
            yield event.plain_result(f"❌ 删除失败: {str(e)}")
    
    @filter.command("admin")
    async def admin_management(self, event: AstrMessageEvent):
        """管理员管理命令"""
        message_parts = event.message_str.strip().split()
        user_openid = self._get_user_openid(event)
        
        if not user_openid:
            yield event.plain_result("❌ 无法获取用户OpenID！")
            return
        
        # 如果没有任何管理员，允许第一个用户成为管理员
        if len(self.admin_openids) == 0:
            if len(message_parts) == 1:
                yield event.plain_result("🔧 系统检测到没有管理员，使用 /admin init 初始化您为管理员")
                return
            
            if message_parts[1] == "init":
                if self._add_admin(user_openid, "初始管理员", "系统初始化"):
                    yield event.plain_result(f"✅ 恭喜！您已成为系统管理员\n🆔 管理员OpenID: {user_openid}")
                else:
                    yield event.plain_result("❌ 初始化管理员失败！")
                return
        
        # 检查权限
        if not self._is_admin(user_openid):
            yield event.plain_result("❌ 您没有管理员权限！")
            return
        
        if len(message_parts) == 1:
            # 显示管理员帮助
            help_text = """🔧 管理员命令帮助\n\n"""
            help_text += "📋 可用命令:\n"
            help_text += "• /admin list - 查看管理员列表\n"
            help_text += "• /admin add <OpenID> [用户名] - 添加管理员\n"
            help_text += "• /admin remove <OpenID> - 移除管理员\n"
            help_text += "• /admin info - 查看当前用户信息\n"
            help_text += "\n💡 提示: 只有管理员才能执行这些命令"
            yield event.plain_result(help_text)
            return
        
        command = message_parts[1].lower()
        
        if command == "list":
            # 查看管理员列表
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT openid, username, created_at, created_by FROM admin_users ORDER BY created_at')
                results = cursor.fetchall()
                conn.close()
                
                if not results:
                    yield event.plain_result("📋 暂无管理员")
                    return
                
                response = "👑 管理员列表\n\n"
                for i, (openid, username, created_at, created_by) in enumerate(results, 1):
                    response += f"{i}. {username or '未命名'}\n"
                    response += f"   OpenID: {openid}\n"
                    response += f"   添加时间: {created_at[:19]}\n"
                    response += f"   添加者: {created_by or '未知'}\n\n"
                
                yield event.plain_result(response)
                
            except Exception as e:
                yield event.plain_result(f"❌ 查询管理员列表失败: {str(e)}")
        
        elif command == "add":
            # 添加管理员
            if len(message_parts) < 3:
                yield event.plain_result("❌ 请提供要添加的OpenID！\n使用方法: /admin add <OpenID> [用户名]")
                return
            
            target_openid = message_parts[2]
            username = ' '.join(message_parts[3:]) if len(message_parts) > 3 else None
            
            if target_openid in self.admin_openids:
                yield event.plain_result(f"❌ OpenID {target_openid} 已经是管理员！")
                return
            
            if self._add_admin(target_openid, username, user_openid):
                response = f"✅ 成功添加管理员！\n"
                response += f"🆔 OpenID: {target_openid}\n"
                response += f"👤 用户名: {username or '未设置'}\n"
                response += f"🔧 添加者: {user_openid}"
                yield event.plain_result(response)
            else:
                yield event.plain_result("❌ 添加管理员失败！")
        
        elif command == "remove":
            # 移除管理员
            if len(message_parts) < 3:
                yield event.plain_result("❌ 请提供要移除的OpenID！\n使用方法: /admin remove <OpenID>")
                return
            
            target_openid = message_parts[2]
            
            if target_openid == user_openid:
                yield event.plain_result("❌ 不能移除自己的管理员权限！")
                return
            
            if target_openid not in self.admin_openids:
                yield event.plain_result(f"❌ OpenID {target_openid} 不是管理员！")
                return
            
            if self._remove_admin(target_openid):
                yield event.plain_result(f"✅ 成功移除管理员: {target_openid}")
            else:
                yield event.plain_result("❌ 移除管理员失败！")
        
        elif command == "info":
            # 查看当前用户信息
            response = f"👤 当前用户信息\n"
            response += f"🆔 OpenID: {user_openid}\n"
            response += f"👑 管理员权限: {'是' if self._is_admin(user_openid) else '否'}\n"
            response += f"📊 系统管理员总数: {len(self.admin_openids)}"
            yield event.plain_result(response)
        
        else:
            yield event.plain_result(f"❌ 未知的管理员命令: {command}\n使用 /admin 查看帮助")
    
    @filter.command("zc")
    async def query_group_server(self, event: AstrMessageEvent):
        """查询当前群聊绑定的服务器或设置群聊服务器"""
        message_parts = event.message_str.strip().split()
        
        # 获取群号
        group_id = getattr(event, 'group_id', None) or getattr(event, 'session_id', 'private')
        if not group_id or group_id == 'private':
            yield event.plain_result("❌ 此命令只能在群聊中使用！")
            return
        
        group_id = str(group_id)
        
        # 如果只有/zc命令，查询当前群聊绑定的服务器
        if len(message_parts) == 1:
            server_info = self._get_group_server(group_id)
            if not server_info:
                yield event.plain_result(f"❌ 当前群聊(OpenID: {group_id})还没有绑定服务器！\n使用方法: /zc <服务器IP> [端口] [服务器名称]")
                return
            
            server_ip, server_port, server_name = server_info
            try:
                query_result = await self.query_scpsl_server(server_ip, server_port)
                if query_result:
                    response = f"🎮 群聊服务器状态\n"
                    response += f"🏷️ 服务器: {server_name or f'{server_ip}:{server_port}'}\n"
                    response += f"👥 在线人数: {query_result.get('players', 'N/A')}/{query_result.get('max_players', 'N/A')}\n"
                    response += f"🔄 状态: 🟢 在线"
                    yield event.plain_result(response)
                else:
                    yield event.plain_result(f"❌ 无法连接到群聊服务器 {server_ip}:{server_port}\n🔄 状态: 🔴 离线")
            except Exception as e:
                yield event.plain_result(f"❌ 查询群聊服务器时出错: {str(e)}")
            return
        
        # 设置群聊服务器
        if len(message_parts) < 2:
            yield event.plain_result("请提供服务器IP地址！\n使用方法: /zc <服务器IP> [端口] [服务器名称]")
            return
        
        server_ip = message_parts[1]
        
        # 解析端口参数
        server_port = self.default_port
        server_name = None
        
        if len(message_parts) > 2:
            try:
                server_port = int(message_parts[2])
                if not (1 <= server_port <= 65535):
                    yield event.plain_result("❌ 端口号必须在1-65535之间！")
                    return
            except ValueError:
                # 如果第三个参数不是数字，当作服务器名称处理
                server_name = ' '.join(message_parts[2:])
        
        if len(message_parts) > 3 and server_name is None:
            server_name = ' '.join(message_parts[3:])
        
        # 测试服务器连接
        try:
            test_result = await self.query_scpsl_server(server_ip, server_port)
            if not test_result:
                yield event.plain_result(f"⚠️ 警告: 无法连接到服务器 {server_ip}:{server_port}，但仍会保存设置")
        except Exception as e:
            yield event.plain_result(f"⚠️ 警告: 测试连接时出错 ({str(e)})，但仍会保存设置")
        
        # 保存到数据库
        if self._set_group_server(group_id, server_ip, server_port, server_name):
            response = f"✅ 群聊服务器设置成功！\n"
            response += f"🆔 群聊OpenID: {group_id}\n"
            response += f"🏷️ 服务器: {server_name or f'{server_ip}:{server_port}'}\n"
            response += f"💡 使用 /zc 查询服务器状态"
            yield event.plain_result(response)
        else:
            yield event.plain_result("❌ 设置群聊服务器失败，请稍后重试")
    
    @filter.command("scpsl_help")
    async def show_help(self, event: AstrMessageEvent):
        """显示插件帮助信息"""
        help_text = """🎮 SCP:SL 服务器查询插件帮助

📋 可用命令:
• /servers - 显示预设服务器列表
• /xy - 查询所有椿雨服务器状态总览
• /cx <IP> [端口] - 查询自定义服务器状态
• /zc [IP] [端口] [名称] - 群聊服务器管理
• /openid - 获取当前群聊的OpenID
• /myid - 获取当前用户的OpenID
• /groups - 列出所有已绑定服务器的群聊
• /unbind [群聊ID] - 解绑服务器(无参数解绑当前群聊)
• /admin <子命令> - 管理员系统
• /scpsl_help - 显示此帮助信息

👑 管理员命令:
• /admin init - 初始化第一个管理员(仅无管理员时可用)
• /admin list - 列出所有管理员
• /admin add <OpenID> [用户名] - 添加管理员
• /admin remove <OpenID> - 移除管理员
• /admin info - 查看当前用户信息

🤖 自动功能:
• 发送包含"炸了?"或"服务器炸了?"的消息会自动检测所有预设服务器状态

📝 使用示例:
• /servers - 查看所有预设服务器
• /xy - 查询所有椿雨服务器状态
• /cx 127.0.0.1 - 查询自定义服务器
• /zc - 查询当前群聊绑定的服务器
• /zc 192.168.1.100 7777 我的服务器 - 设置群聊服务器
• /openid - 获取当前群聊的OpenID
• /myid - 获取当前用户的OpenID和权限信息
• /groups - 查看所有已绑定服务器的群聊
• /unbind - 解绑当前群聊的服务器
• /unbind 123456 - 删除指定群聊(ID:123456)的绑定
• /admin add 12345678 张三 - 添加管理员
• 服务器炸了? - 自动检测所有服务器

💡 提示:
• 默认端口为7777
• 支持TCP和UDP查询
• 查询超时时间为5秒
• 预设服务器可快速查询
• /zc、/openid、/unbind命令只能在群聊中使用
• /myid命令可在任何地方使用，显示用户身份和权限
• 每个群聊可以绑定一个专属服务器
• OpenID用于唯一标识不同的群聊和用户
• /groups命令可查看所有群聊的绑定情况
• /unbind可以解绑当前群聊或删除其他群聊的绑定
• 管理员可以管理所有群聊的服务器绑定
• 普通用户只能管理自己群聊的服务器绑定
• 使用/admin init初始化第一个管理员
"""
        yield event.plain_result(help_text)
    
    async def terminate(self):
        """插件卸载时调用"""
        logger.info("SCP:SL服务器查询插件已卸载")