#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立测试SCPSL服务器查询功能
用于验证A2S协议challenge机制的修复
不依赖astrbot框架
"""

import socket
import struct
import asyncio
import time
from typing import Dict, Any

class SCPSLQueryTester:
    """SCPSL服务器查询测试器"""
    
    def __init__(self):
        self.timeout = 5.0
    
    async def _query_server_tcp(self, ip: str, port: int) -> Dict[str, Any]:
        """使用支持challenge的A2S协议查询服务器信息"""
        # 尝试多个可能的查询端口
        query_ports = [port, port + 1, port - 1]
        
        for query_port in query_ports:
            sock = None
            try:
                # 创建UDP socket进行A2S查询
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.timeout)  # 增加超时时间以适应challenge机制
                
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
                    print(f"🔑 收到challenge响应，端口: {query_port}")
                    if len(response) >= 9:
                        # 提取challenge值
                        challenge = struct.unpack('<I', response[5:9])[0]
                        print(f"🔑 Challenge值: {challenge}")
                        
                        # 重新发送带challenge的查询
                        query_with_challenge = query + struct.pack('<I', challenge)
                        sock.sendto(query_with_challenge, (ip, query_port))
                        response, addr = sock.recvfrom(1400)
                        print(f"✅ 成功发送challenge响应")
                    else:
                        # challenge响应格式错误
                        print(f"❌ Challenge响应格式错误")
                        continue
                
                ping = round((time.time() - start_time) * 1000)
                
                # 解析A2S_INFO响应
                if len(response) >= 5 and response[4] == 0x49:  # A2S_INFO response
                    print(f"📋 收到A2S_INFO响应，端口: {query_port}")
                    result = self._parse_a2s_info(response[5:], ping)
                    if result.get('status') == 'online':
                        return result
                
            except socket.timeout:
                print(f"⏰ 查询超时: {ip}:{query_port}")
                continue
            except ConnectionRefusedError:
                print(f"🚫 连接被拒绝: {ip}:{query_port}")
                continue
            except Exception as e:
                print(f"❌ 查询异常 {ip}:{query_port}: {str(e)}")
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

async def test_server_query():
    """测试服务器查询功能"""
    print("🔧 开始测试SCPSL服务器查询功能...\n")
    
    # 创建查询实例
    tester = SCPSLQueryTester()
    
    # 测试服务器列表
    test_servers = [
        ("43.139.108.159", 8000, "椿雨纯净服#1"),
        ("43.139.108.159", 8001, "椿雨纯净服#2"),
        ("43.139.108.159", 8002, "椿雨插件服#1"),
        ("43.139.108.159", 8003, "椿雨插件服#2"),
        ("43.139.108.159", 7777, "椿雨萌新服"),
        ("8.138.236.97", 5000, "银狼服务器")
    ]
    
    successful_queries = 0
    total_queries = len(test_servers)
    
    for ip, port, name in test_servers:
        print(f"🔍 正在查询: {name} ({ip}:{port})")
        print("-" * 50)
        
        try:
            # 使用修改后的查询方法
            result = await tester.query_scpsl_server(ip, port)
            
            if result and result.get('online'):
                print(f"✅ {name}: 在线")
                print(f"   👥 玩家: {result.get('players', 'N/A')}/{result.get('max_players', 'N/A')}")
                print(f"   🌐 延迟: {result.get('ping', 'N/A')}ms")
                print(f"   🏷️ 服务器名: {result.get('name', 'N/A')}")
                print(f"   🗺️ 地图: {result.get('map', 'N/A')}")
                successful_queries += 1
            else:
                print(f"❌ {name}: 离线或无响应")
                
        except Exception as e:
            print(f"❌ {name}: 查询失败 - {str(e)}")
        
        print()  # 空行分隔
    
    # 输出测试结果统计
    print("="*50)
    print("📊 测试结果统计:")
    print(f"   成功查询: {successful_queries}/{total_queries}")
    print(f"   成功率: {(successful_queries/total_queries)*100:.1f}%")
    
    if successful_queries > 0:
        print("\n🎉 A2S协议challenge机制修复成功！")
        print("💡 建议: 如果某些服务器仍然无法查询，可能是服务器配置或网络问题。")
    else:
        print("\n⚠️ 所有服务器查询都失败了，可能需要进一步调试。")
        print("💡 建议: 检查网络连接和服务器状态。")

if __name__ == "__main__":
    print("🎮 SCPSL 14.1.4 服务器查询测试工具")
    print("=" * 50)
    
    try:
        # 运行基本查询测试
        asyncio.run(test_server_query())
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n🏁 测试完成")