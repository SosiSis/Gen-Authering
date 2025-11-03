# streamlit_app.py - Enhanced Production-Ready Multi-Agent UI
"""
Production-ready Streamlit application for the Multi-Agent Publication Generator.
This is the main entry point with enhanced error handling, security, and user experience.
"""

import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ui.enhanced_streamlit_app import MultiAgentUI
    from utils.logging_config import setup_logging
    import streamlit as st
    
    # Initialize logging
    setup_logging()
    
    # Create and run the enhanced UI
    if __name__ == "__main__":
        app = MultiAgentUI()
        app.run()
        
except ImportError as e:
    # Fallback to basic UI if enhanced version fails
    st.error(f"⚠️ Enhanced UI unavailable: {e}")
    st.markdown("## 🔄 Fallback Mode")
    st.info("Running in basic mode. Some features may be limited.")
    
    # Basic fallback implementation
    import streamlit as st
    import os
    
    try:
        from agents.nodes import create_mcp_message
        from agents.graph_spec import build_graph
        
        # Initialize coordinator
        coordinator = build_graph()
        
        st.set_page_config(
            page_title="Multi-Agent Publication Generator", 
            page_icon="📚",
            layout="wide"
        )
        st.title("📚 Multi-Agent Publication Generator")
        st.warning("⚠️ Running in basic fallback mode")
        
        # Basic session state
        if "conversation_id" not in st.session_state:
            st.session_state.conversation_id = None
        if "md_path" not in st.session_state:
            st.session_state.md_path = None
        if "pdf_path" not in st.session_state:
            st.session_state.pdf_path = None
        
        # URL input
        repo_url = st.text_input("GitHub Repository URL:")
        
        # Pipeline control
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Start Pipeline") and repo_url:
                try:
                    with st.spinner("Processing..."):
                        msg = create_mcp_message(
                            role="agent", 
                            name="RepoNode", 
                            content={"repo_url": repo_url}
                        )
                        st.session_state.conversation_id = msg["metadata"]["conversation_id"]
                        coordinator.send(msg)
                        coordinator.run_once()
                        coordinator.run_once()
                        
                        # Check for results
                        events = coordinator.get_conversation_events(st.session_state.conversation_id)
                        draft = next((e for e in events if e.get("content", {}).get("status") == "draft_ready"), None)
                        
                        if draft:
                            st.session_state.md_path = draft["content"]["md_path"]
                            st.success("✅ Draft generated successfully!")
                        else:
                            st.error("❌ Draft generation failed")
                            
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col2:
            if st.session_state.md_path and st.button("📊 Evaluate Quality"):
                try:
                    eval_msg = create_mcp_message(
                        role="agent",
                        name="EvaluatorNode",
                        content={"md_path": st.session_state.md_path},
                        conversation_id=st.session_state.conversation_id
                    )
                    coordinator.send(eval_msg)
                    coordinator.run_once()
                    
                    events = coordinator.get_conversation_events(st.session_state.conversation_id)
                    eval_done = next((e for e in events if e.get("content", {}).get("status") == "eval_done"), None)
                    
                    if eval_done and eval_done["content"].get("flesch_reading_ease"):
                        st.metric("Readability Score", f"{eval_done['content']['flesch_reading_ease']:.1f}")
                    
                except Exception as e:
                    st.error(f"❌ Evaluation error: {str(e)}")
        
        # Editor
        if st.session_state.md_path and os.path.exists(st.session_state.md_path):
            st.markdown("## 📝 Document Editor")
            
            try:
                with open(st.session_state.md_path, 'r', encoding='utf-8') as f:
                    md_text = f.read()
                
                edited = st.text_area("Edit document:", value=md_text, height=400)
                
                col3, col4 = st.columns(2)
                
                with col3:
                    if st.button("💾 Save Changes"):
                        try:
                            with open(st.session_state.md_path, 'w', encoding='utf-8') as f:
                                f.write(edited)
                            st.success("✅ Changes saved!")
                        except Exception as e:
                            st.error(f"❌ Save error: {str(e)}")
                
                with col4:
                    if st.button("📄 Generate PDF"):
                        try:
                            pdf_msg = create_mcp_message(
                                role="agent",
                                name="PDFNode",
                                content={"md_path": st.session_state.md_path},
                                conversation_id=st.session_state.conversation_id
                            )
                            coordinator.send(pdf_msg)
                            coordinator.run_once()
                            
                            events = coordinator.get_conversation_events(st.session_state.conversation_id)
                            pdf_ready = next((e for e in events if e.get("content", {}).get("status") == "pdf_ready"), None)
                            
                            if pdf_ready:
                                st.session_state.pdf_path = pdf_ready["content"]["pdf_path"]
                                st.success("✅ PDF generated!")
                            
                        except Exception as e:
                            st.error(f"❌ PDF generation error: {str(e)}")
                
                # PDF download
                if st.session_state.pdf_path and os.path.exists(st.session_state.pdf_path):
                    try:
                        with open(st.session_state.pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        
                        st.download_button(
                            label="⬇️ Download PDF",
                            data=pdf_bytes,
                            file_name=os.path.basename(st.session_state.pdf_path),
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"❌ Download error: {str(e)}")
                        
            except Exception as e:
                st.error(f"❌ Editor error: {str(e)}")
        
        # Footer
        st.markdown("---")
        st.markdown("⚠️ **Basic Mode Active** - Limited functionality available")
        
    except Exception as e:
        st.error(f"❌ Critical error: {str(e)}")
        st.markdown("Please check the application setup and try again.")

except Exception as e:
    # Final fallback
    print(f"Critical startup error: {e}")
    if 'st' in locals():
        st.error("❌ Application failed to start. Please check the configuration.")
    else:
        print("Streamlit not available. Please install requirements.")
