"""
Multi-Agent Publication Generator - Production-Ready Streamlit App
This is the main entry point with comprehensive error handling and fallback mechanisms.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import Streamlit first
import streamlit as st

# Set page config ONCE at the very top
st.set_page_config(
    page_title="Multi-Agent Publication Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Multi-Agent Publication Generator - Transform GitHub repos into research papers"
    }
)

def load_enhanced_ui():
    """Attempt to load and run the enhanced UI"""
    try:
        # Check environment first - try both env vars and Streamlit secrets
        api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
        
        if not api_key:
            st.error("🔑 GROQ_API_KEY is required")
            st.markdown("""
            ### 🔧 Configuration Required
            
            **For Streamlit Cloud:**
            1. Go to your app dashboard
            2. Click "Settings" → "Secrets"
            3. Add: `GROQ_API_KEY = "your_api_key_here"`
            
            **For Local Development:**
            Create a `.streamlit/secrets.toml` file with:
            ```toml
            GROQ_API_KEY = "your_api_key_here"
            ```
            """)
            return False
        else:
            # Set the environment variable for child processes
            os.environ["GROQ_API_KEY"] = api_key
            
        # Import the enhanced UI components
        from ui.enhanced_streamlit_app import create_enhanced_app
        from utils.logging_config import setup_logging
        
        # Initialize logging
        setup_logging()
        
        # Run the enhanced app
        create_enhanced_app()
        return True
        
    except ImportError as e:
        st.error(f"⚠️ Enhanced UI import failed: {e}")
        return False
    except Exception as e:
        st.error(f"⚠️ Enhanced UI error: {e}")
        st.warning("Falling back to basic mode...")
        return False

def create_basic_ui():
    """Create a basic fallback UI"""
    # Header
    st.markdown("""
    # 📚 Multi-Agent Publication Generator
    ### 🔄 Basic Mode Active
    
    **Note:** Running in basic mode due to enhanced UI issues. Some features may be limited.
    """)
    
    # System status
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🤖 System", "Basic Mode", "Operational")
    with col2:
        st.metric("🔒 Security", "Active", "✓")
    with col3:
        st.metric("📊 Status", "Ready", "✓")
    
    st.markdown("---")
    
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
        if st.button("🚀 Generate Publication", key="basic_generate_btn") and repo_url:
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
        if not load_enhanced_ui():
            # Fall back to basic UI
            create_basic_ui()
    except Exception as e:
        st.error("❌ Application failed to start. Please check the configuration.")
        st.exception(e)

if __name__ == "__main__":
    main()
