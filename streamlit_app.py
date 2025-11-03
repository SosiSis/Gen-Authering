# streamlit_app.py - Enhanced Production-Ready Multi-Agent UI
"""
Production-ready Streamlit application for the Multi-Agent Publication Generator.
This is the main entry point with enhanced error handling, security, and user experience.
"""

import sys
import os
from pathlib import Path
import streamlit as st

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set page config first (before any other Streamlit calls)
st.set_page_config(
    page_title="Multi-Agent Publication Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

def run_enhanced_ui():
    """Try to run the enhanced UI"""
    try:
        from ui.enhanced_streamlit_app import MultiAgentUI
        from utils.logging_config import setup_logging
        
        # Initialize logging
        setup_logging()
        
        # Create and run the enhanced UI
        app = MultiAgentUI()
        app.run()
        return True
        
    except Exception as e:
        st.error(f"⚠️ Enhanced UI error: {e}")
        st.warning("Falling back to basic mode...")
        return False

def run_basic_ui():
    """Run the basic fallback UI"""
    st.title("📚 Multi-Agent Publication Generator")
    st.markdown("## 🔄 Basic Mode")
    st.info("Running in basic mode. Some features may be limited.")
    
    try:
        from agents.nodes import create_mcp_message
        from agents.graph_spec import build_graph
        
        # Initialize coordinator
        coordinator = build_graph()
        
        # Basic session state
        if "conversation_id" not in st.session_state:
            st.session_state.conversation_id = None
        if "md_path" not in st.session_state:
            st.session_state.md_path = None
        if "pdf_path" not in st.session_state:
            st.session_state.pdf_path = None
        
        # URL input
        repo_url = st.text_input("GitHub Repository URL:")
        
        # Simple pipeline control
        if st.button("🚀 Generate Publication") and repo_url:
            try:
                with st.spinner("Processing repository..."):
                    msg = create_mcp_message(
                        role="agent", 
                        name="RepoNode", 
                        content={"repo_url": repo_url}
                    )
                    st.session_state.conversation_id = msg["metadata"]["conversation_id"]
                    coordinator.send(msg)
                    coordinator.run_once()
                    
                    st.success("✅ Basic processing completed!")
                    st.info("Enhanced features available in full mode.")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        
        # Footer
        st.markdown("---")
        st.markdown("⚠️ **Basic Mode Active** - Enhanced features available when full system loads")
        
    except Exception as e:
        st.error(f"❌ Critical error: {str(e)}")
        st.markdown("Please check the application setup and try again.")

# Main execution
def main():
    """Main application entry point"""
    try:
        # Try enhanced UI first
        if not run_enhanced_ui():
            # Fall back to basic UI
            run_basic_ui()
    except Exception as e:
        st.error("❌ Application failed to start. Please check the configuration.")
        st.exception(e)

if __name__ == "__main__":
    main()
