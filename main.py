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

@register("scpsl_server_query", "若梦", "SCP:SL服务器查询插件，仿照server_Qchat功能", "1.0.0")
class SCPSLServerQuery(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.default_port = 7777
        self.timeout = 5
        self.db_path = os.path.join(os.path.dirname(__file__), 'group_servers.db')
        self._init_database()
        
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
• 椿雨萌新服#1: 175.178.37.128:7777
• 椿雨纯净服#1: 27.45.5.146:7777
• 椿雨纯净服#2: 27.45.5.146:7778
• 椿雨插件服#1: 27.45.5.146:7779
• 椿雨插件服#2: 27.45.5.146:7780
• 椿雨怀旧服#1: 175.178.37.128:7778

📝 使用方法:
• /xy - 查询所有椿雨服务器状态
• /cx <IP:端口> - 查询自定义服务器"""
        yield event.plain_result(server_list)
    
    @filter.command("xy")
    async def query_chunyu_servers(self, event: AstrMessageEvent):
        """查询所有椿雨服务器状态"""
        servers = [
            ("27.45.5.146", 7777, "椿雨纯净服#1"),
            ("27.45.5.146", 7778, "椿雨纯净服#2"),
            ("27.45.5.146", 7779, "椿雨插件服#1"),
            ("27.45.5.146", 7780, "椿雨插件服#2"),
            ("175.178.37.128", 7777, "椿雨萌新服#1")
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
            ("27.45.5.146", 7777, "椿雨纯净服#1"),
            ("27.45.5.146", 7778, "椿雨纯净服#2"),
            ("27.45.5.146", 7779, "椿雨插件服#1"),
            ("27.45.5.146", 7780, "椿雨插件服#2"),
            ("175.178.37.128", 7777, "椿雨萌新服#1")
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
        """使用A2S协议查询服务器信息"""
        # 尝试多个可能的查询端口
        query_ports = [port, port + 1, port - 1]
        
        for query_port in query_ports:
            try:
                # 创建UDP socket进行A2S查询
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(3.0)  # 减少超时时间
                
                start_time = time.time()
                
                # A2S_INFO查询
                query = b"\xFF\xFF\xFF\xFF\x54Source Engine Query\x00"
                sock.sendto(query, (ip, query_port))
                
                response, addr = sock.recvfrom(1400)
                ping = round((time.time() - start_time) * 1000)
                
                sock.close()
                
                if len(response) < 6:
                    continue
                
                # 检查响应头
                if response[:4] != b"\xFF\xFF\xFF\xFF":
                    continue
                
                # 检查是否是挑战响应
                if response[4] == 0x41:  # S2C_CHALLENGE
                    if len(response) >= 9:
                        challenge = struct.unpack('<I', response[5:9])[0]
                        # 重新发送带挑战的查询
                        query_with_challenge = query + struct.pack('<I', challenge)
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(3.0)
                        sock.sendto(query_with_challenge, (ip, query_port))
                        response, addr = sock.recvfrom(1400)
                        sock.close()
                
                # 解析A2S_INFO响应
                if response[4] == 0x49:  # A2S_INFO response
                    result = self._parse_a2s_info(response[5:], ping)
                    if result.get('status') == 'online':
                        return result
                
            except socket.timeout:
                continue
            except ConnectionRefusedError:
                continue
            except Exception as e:
                continue
        
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
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
    
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
                yield event.plain_result(f"❌ 当前群聊({group_id})还没有绑定服务器！\n使用方法: /zc <服务器IP> [端口] [服务器名称]")
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
• /scpsl_help - 显示此帮助信息

🤖 自动功能:
• 发送包含"炸了?"或"服务器炸了?"的消息会自动检测所有预设服务器状态

📝 使用示例:
• /servers - 查看所有预设服务器
• /xy - 查询所有椿雨服务器状态
• /cx 127.0.0.1 - 查询自定义服务器
• /zc - 查询当前群聊绑定的服务器
• /zc 192.168.1.100 7777 我的服务器 - 设置群聊服务器
• 服务器炸了? - 自动检测所有服务器

💡 提示:
• 默认端口为7777
• 支持TCP和UDP查询
• 查询超时时间为5秒
• 预设服务器可快速查询
• /zc命令只能在群聊中使用
• 每个群聊可以绑定一个专属服务器
"""
        yield event.plain_result(help_text)
    
    async def terminate(self):
        """插件卸载时调用"""
        logger.info("SCP:SL服务器查询插件已卸载")