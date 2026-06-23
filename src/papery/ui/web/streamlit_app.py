import streamlit as st

st.set_page_config(page_title="Agentic LLM Chat", page_icon="🤖", layout="centered")

st.title("🤖 Agentic LLM Conversational Interface")

# Session state for chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display chat history
for message in st.session_state["messages"]:
    if message["role"] == "user":
        st.chat_message("user").write(message["content"])
    else:
        st.chat_message("assistant").write(message["content"])

# User input
user_input = st.chat_input("Type your message and press Enter...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    # Placeholder for LLM response (to be implemented)
    st.session_state["messages"].append({"role": "assistant", "content": "[LLM response will appear here]"})
    st.rerun()
