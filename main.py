import asyncio
import uuid
import traceback
import streamlit as st
from typing import Union
from langchain_core.messages import HumanMessage
from src.api.graph import graph
from pathlib import Path
import json
import os
import logging
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "main.log")

logger = logging.getLogger("mcp_main")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler(LOG_FILE, when="W0", interval=1, backupCount=4, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(handler)

default_mcp_config = {
        "command": "python",
        "args": [Path(__file__).parent.parent.parent / "src/api/math_server.py"]
}
CONFIG_DIR = "config"
CONFIG_PATH = os.path.join(CONFIG_DIR, "mcp_config.json")

json_config = json.load(open(CONFIG_PATH))

def detect_transport(config: dict) -> str:
    if "command" in config and "args" in config:
        return "stdio"
    elif "url" in config:
        return "sse"
    else:
        raise ValueError("Unknown transport type: cannot determine from config")

if "mcp_config_dict" not in st.session_state:
    st.session_state["mcp_config_dict"]={}
    for name, config in json_config.items():
        try:
            config["transport"] = detect_transport(config)
        except Exception as e:
            logger.error(f"Transport detection failed for '{name}': {e}")
            continue
        st.session_state["mcp_config_dict"][name] = config
    if 'math' not in st.session_state["mcp_config_dict"]:
        st.session_state["mcp_config_dict"]['math'] = default_mcp_config


st.set_page_config(page_title="LangChain React Agent", page_icon=":shark:")
st.title("LangChain React Agent")
# Function to display chat history in the sidebar
def display_named_mcp_config():
    st.sidebar.title("⚙️ MCP 설정 목록")

    if "mcp_config_dict" not in st.session_state:
        st.session_state["mcp_config_dict"] = {}

    if "mcp_enabled_dict" not in st.session_state:
        st.session_state["mcp_enabled_dict"] = {}

    with st.sidebar.expander("➕ 새로운 MCP 설정 추가"):
        mcp_name = st.text_input("📛 MCP 이름 (유일한 키)", key="mcp_name_input")

        mode = st.selectbox("🔌 MCP 종류", ["stdio", "sse"], key="mcp_mode_select")

        if mode == "stdio":
            cmd = st.text_input("🛠️ 실행 명령어 (command)", key="mcp_stdio_cmd")
            args = st.text_input("📦 인자 (argument)", key="mcp_stdio_args")
            env_input = st.text_input("🌿 환경 변수 (k=v,k2=v2 형태)", key="mcp_stdio_env")
            new_config = {
                "command": cmd,
                "args": args.strip().split()
            }
            if env_input.strip():
                env_dict = dict(pair.split("=", 1) for pair in env_input.split(",") if "=" in pair)
                new_config["env"] = env_dict
        else:  # sse
            url = st.text_input("🌐 SSE URL", key="mcp_sse_url")
            new_config = {
                "url": url.strip()
            }

        if st.button("✅ 설정 저장"):
            if not mcp_name:
                st.warning("MCP 이름을 입력해주세요.")
            elif mcp_name in st.session_state["mcp_config_dict"]:
                st.warning("이미 존재하는 MCP 이름입니다.")
            elif mcp_name == "math":
                st.warning("'math'는 예약된 MCP 이름입니다.")
            else:
                st.session_state["mcp_config_dict"][mcp_name] = new_config
                st.success(f"'{mcp_name}' 설정이 저장되었습니다!")

    # 설정 목록 보여주기
    for name, config in st.session_state["mcp_config_dict"].items():
        with st.sidebar.expander(f"🔧 {name}"):
            if 'cmd' in config:
                st.text(f"CMD: {config['command']}")
                st.text(f"ARG: {config['args']}")
                if "env" in config:
                    st.text(f"ENV: {config['env']}")
            elif 'url' in config:
                st.text(f"URL: {config['url']}")
                if "env" in config:
                    st.text(f"ENV: {config['env']}")
            elif name == "math":
                st.text("기본 내장 도구 (항상 활성화됨)")

            # 사용 여부 체크박스 (math 제외)
            if name == "math":
                st.session_state["mcp_enabled_dict"][name] = True
            else:
                enabled = st.checkbox(f"✅ 사용", key=f"enable_{name}", value=st.session_state["mcp_enabled_dict"].get(name, True))
                st.session_state["mcp_enabled_dict"][name] = enabled

            # 삭제 버튼 (math 제외)
            if name != "math":
                if st.button(f"🗑️ 삭제 - {name}", key=f"delete_{name}"):
                    del st.session_state["mcp_config_dict"][name]
                    if name in st.session_state["mcp_enabled_dict"]:
                        del st.session_state["mcp_enabled_dict"][name]
                    st.experimental_rerun()

def save_mcp_config_dict_to_file():
    config_dict = st.session_state.get("mcp_config_dict", {})

    if "math" not in config_dict and "math" in st.session_state.get("mcp_config_dict", {}):
        config_dict["math"] = st.session_state["mcp_config_dict"]["math"]

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)

    st.sidebar.success(f"✅ 설정이 '{CONFIG_PATH}'에 저장되었습니다.")
    

st.sidebar.title("MCP Tools")
display_named_mcp_config()
# 기존 MCP 설정 목록 및 추가 UI 그린 후에 하단에 추가
if st.sidebar.button("💾 설정 전체 저장"):
    save_mcp_config_dict_to_file()
    
class ChatProcessor:
    def __init__(self):
        self.messages = st.session_state.messages
        self.graph = graph
    def add_message(self, role: str, content: str):
        """메시지를 대화 기록에 추가"""
        self.messages.append({"role": role, "content": content})
        
    def display_message(self, role: str, content: str):
        """메시지를 화면에 표시"""
        with st.chat_message(role):
            st.write(content)

    async def process_response(self, prompt: str, streaming: bool = True):
        """응답 처리를 위한 공통 함수"""
        if not prompt:
            return "검색어를 입력해주세요."
            
        try:
            if streaming:
                return await self._process_streaming(prompt)
            else:
                return await self._process_sync(prompt)
        except Exception as e:
            logger.error(f"Error in process_response: {str(e)}")
            logger.error(traceback.format_exc())
            return f"오류가 발생했습니다: {str(e)}"
            
    async def _process_streaming(self, prompt: str) -> str:
        """스트리밍 응답 처리"""
        response_container = st.empty()
        full_response = []
        # 시스템 메시지 
        session_id = st.session_state.session_id
        logger.info(f"session_id: {session_id}")

        enabled_mcp_config = {
            name: config for name, config in st.session_state["mcp_config_dict"].items()
            if st.session_state["mcp_enabled_dict"].get(name, False)
        }

        async for chunk in self.graph.astream(
            {"messages": [HumanMessage(content=prompt)],
             "mcp_config": enabled_mcp_config
            }, 
            {"thread_id": session_id }
        ):
            # logger.info(f"chunk: {chunk}")
            last_message = chunk['chat_node']['messages'][-1]
            full_response.append(last_message.content)
            logger.info(last_message.content)
            response_container.write("".join(full_response))

        return "".join(full_response)

    async def _process_sync(self, prompt: str) -> str:
        """동기식 응답 처리"""
        return await self.graph.invoke({"messages": [HumanMessage(content=prompt)]})
        # return await call_with_tool_stream(prompt).__anext__()

# Streamlit 앱 초기화
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요 뭘 도와 드릴까요?"}]
if "chat_processor" not in st.session_state:
    st.session_state.chat_processor = ChatProcessor()

# 기존 메시지 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 사용자 입력 처리
if prompt := st.chat_input():
    processor = st.session_state.chat_processor
    processor.add_message("user", prompt)
    processor.display_message("user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = asyncio.run(processor.process_response(prompt))
            processor.add_message("assistant", response)
