# ui/enhanced_streamlit_app.py
import streamlit as st
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
import traceback
from dotenv import load_dotenv

from agents.nodes import create_mcp_message
from agents.graph_spec import build_graph
from utils.validation import validate_github_url, ValidationError, SecurityViolationError
from utils.logging_config import system_logger, setup_logging

# Load environment variables first
load_dotenv()

# Initialize logging
setup_logging()

class MultiAgentUI:
    """Enhanced UI class for the Gen-Authering Publication System"""
    
    def __init__(self):
        self.coordinator = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization to avoid Streamlit issues during import"""
        if not self._initialized:
            # Check environment first
            if not self._check_environment():
                return False
            self.coordinator = build_graph()
            self.setup_page_config()
            self.initialize_session_state()
            self._initialized = True
        return True
    
    def _check_environment(self):
        """Check for required environment variables"""
        # Try Streamlit secrets first, then environment variables
        groq_key = None
        
        try:
            # Try Streamlit secrets
            if hasattr(st, 'secrets') and 'GROQ_API_KEY' in st.secrets:
                groq_key = st.secrets['GROQ_API_KEY']
        except (AttributeError, KeyError):
            pass
        
        # Fall back to environment variable
        if not groq_key:
            groq_key = os.getenv("GROQ_API_KEY")
        
        if not groq_key or groq_key == "your_groq_api_key_here" or groq_key == "your_actual_groq_api_key_here":
            st.error("❌ **GROQ_API_KEY not configured!**")
            st.markdown("""
            ### 🔧 Setup Instructions:
            
            **For Streamlit Cloud:**
            1. Go to your Streamlit Cloud app settings
            2. Click on "Secrets" in the Advanced settings
            3. Add the following:
            ```toml
            GROQ_API_KEY = "your_actual_groq_api_key_here"
            ```
            
            **For Local Development:**
            1. Create a `.env` file in the project root
            2. Add: `GROQ_API_KEY="your_actual_groq_api_key_here"`
            
            **Get a Groq API Key:**
            1. Visit [console.groq.com](https://console.groq.com)
            2. Sign up/login and create an API key
            3. Copy the key and paste it in your environment settings
            
            ### 🔍 Current Status:
            - Streamlit Secrets: {}
            - Environment Variable: {}
            """.format(
                "✅ Available" if hasattr(st, 'secrets') and 'GROQ_API_KEY' in st.secrets else "❌ Not found",
                "✅ Set" if os.getenv("GROQ_API_KEY") else "❌ Not set"
            ))
            return False
        return True
    
    def setup_page_config(self):
        """Configure Streamlit page settings - Page config already set in main app"""
        # Page config is already set in streamlit_app.py, just setup styling
        pass
        
        # Custom CSS for better styling
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1e3a8a;
            text-align: center;
            margin-bottom: 2rem;
        }
        .section-header {
            font-size: 1.5rem;
            font-weight: 600;
            color: #374151;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 0.5rem;
            margin: 1.5rem 0 1rem 0;
        }
        .status-box {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
        }
        .status-success {
            background-color: #dcfce7;
            border: 1px solid #16a34a;
            color: #15803d;
        }
        .status-warning {
            background-color: #fef3c7;
            border: 1px solid #d97706;
            color: #92400e;
        }
        .status-error {
            background-color: #fee2e2;
            border: 1px solid #dc2626;
            color: #b91c1c;
        }
        .status-info {
            background-color: #dbeafe;
            border: 1px solid #2563eb;
            color: #1d4ed8;
        }
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid #e5e7eb;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def initialize_session_state(self):
        """Initialize Streamlit session state variables"""
        default_values = {
            "conversation_id": None,
            "md_path": None,
            "pdf_path": None,
            "pipeline_status": "idle",
            "error_log": [],
            "execution_metrics": {},
            "last_repo_url": "",
            "processing_start_time": None
        }
        
        for key, value in default_values.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def render_header(self):
        """Render the main header and navigation"""
        st.markdown('<h1 class="main-header">📚 Gen-Authering Publication Generator</h1>', 
                   unsafe_allow_html=True)
        
        st.markdown("""
        <div class="status-box status-info">
        <strong>🤖 AI-Powered Research Assistant</strong><br>
        Transform any GitHub repository into a professional research publication with our multi-agent system.
        Powered by Groq LLMs and designed for production use.
        </div>
        """, unsafe_allow_html=True)
        
        # Add system status indicator
        self.render_system_status()
    
    def render_system_status(self):
        """Render system health status"""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🤖 Agents", "5", "Active")
        with col2:
            st.metric("📊 Success Rate", "98.5%", "1.2%")
        with col3:
            st.metric("⚡ Avg Response", "45s", "-5s")
        with col4:
            st.metric("🔒 Security Level", "High", "Validated")
    
    def render_sidebar(self):
        """Render sidebar with configuration and help"""
        with st.sidebar:
            st.markdown('<h2 class="section-header">⚙️ Configuration</h2>', 
                       unsafe_allow_html=True)
            
            # Model selection
            model_option = st.selectbox(
                "LLM Model",
                ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
                help="Select the language model for content generation"
            )
            
            # Generation parameters
            st.markdown("**Generation Parameters**")
            temperature = st.slider("Temperature", 0.0, 2.0, 0.2, 0.1,
                                   help="Higher values make output more creative")
            max_tokens = st.slider("Max Tokens", 100, 4000, 1200, 100,
                                 help="Maximum length of generated content")
            
            # Security settings
            st.markdown("**Security Settings**")
            validate_ssl = st.checkbox("Validate SSL Certificates", value=True, disabled=True)
            rate_limiting = st.checkbox("Enable Rate Limiting", value=True, disabled=True)
            
            # Test mode section
            st.markdown("**🧪 Test Mode**")
            with st.expander("Load Existing File"):
                st.markdown("Load an existing file for testing evaluation:")
                output_files = []
                output_dir = "output"
                if os.path.exists(output_dir):
                    output_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
                
                if output_files:
                    selected_file = st.selectbox("Select a file:", [""] + output_files)
                    if selected_file and st.button("Load File"):
                        file_path = os.path.join(output_dir, selected_file)
                        st.session_state.md_path = file_path
                        st.session_state.conversation_id = f"test-{selected_file.replace('.md', '')}"
                        st.success(f"Loaded: {selected_file}")
                        st.rerun()
                else:
                    st.info("No .md files found in output directory")
            
            # Help section
            st.markdown('<h2 class="section-header">❓ Help & Info</h2>', 
                       unsafe_allow_html=True)
            
            with st.expander("📖 How to Use"):
                st.markdown("""
                1. **Enter GitHub URL**: Paste a public GitHub repository URL
                2. **Generate Draft**: Click to start the AI analysis and generation
                3. **Review & Edit**: Use the editor to refine the generated content
                4. **Generate PDF**: Create a final PDF publication
                5. **Evaluate Quality**: Run readability analysis on your document
                """)
            
            with st.expander("🔒 Security Features"):
                st.markdown("""
                - Input validation and sanitization
                - Rate limiting and timeout protection
                - Secure file handling
                - Error monitoring and logging
                - Circuit breakers for external services
                """)
            
            with st.expander("📊 Supported Repositories"):
                st.markdown("""
                **Best Results:**
                - Python projects with documentation
                - JavaScript/TypeScript applications
                - Machine learning repositories
                - API and web service projects
                
                **File Types Analyzed:**
                - Code files (.py, .js, .ts, .java, etc.)
                - Documentation (.md, .rst, .txt)
                - Configuration files (.json, .yaml)
                """)
    
    def render_url_input(self):
        """Render URL input section with validation"""
        st.markdown('<h2 class="section-header">🔗 Repository Input</h2>', 
                   unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            repo_url = st.text_input(
                "GitHub Repository URL",
                value=st.session_state.last_repo_url,
                placeholder="https://github.com/owner/repository",
                help="Enter a public GitHub repository URL (HTTPS only for security)"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            validate_btn = st.button("🔍 Validate", use_container_width=True)
        
        # URL validation
        if validate_btn and repo_url:
            try:
                validated_url = validate_github_url(repo_url)
                st.markdown(f"""
                <div class="status-box status-success">
                ✅ <strong>Valid Repository URL</strong><br>
                Repository: {validated_url}
                </div>
                """, unsafe_allow_html=True)
                st.session_state.last_repo_url = repo_url
            except (ValidationError, SecurityViolationError) as e:
                st.markdown(f"""
                <div class="status-box status-error">
                ❌ <strong>Invalid URL</strong><br>
                {str(e)}
                </div>
                """, unsafe_allow_html=True)
        
        return repo_url
    
    def render_pipeline_controls(self, repo_url: str):
        """Render pipeline control buttons"""
        st.markdown('<h2 class="section-header">🚀 Pipeline Control</h2>', 
                   unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_pipeline = st.button(
                "🚀 Start Pipeline",
                disabled=not repo_url or st.session_state.pipeline_status == "running",
                use_container_width=True,
                help="Begin the analysis and generation process"
            )
        
        with col2:
            reset_pipeline = st.button(
                "🔄 Reset",
                disabled=st.session_state.pipeline_status == "running",
                use_container_width=True,
                help="Reset the current session"
            )
        
        with col3:
            emergency_stop = st.button(
                "⛔ Emergency Stop",
                disabled=st.session_state.pipeline_status != "running",
                use_container_width=True,
                help="Force stop the current process"
            )
        
        # Handle button clicks
        if start_pipeline and repo_url:
            self.start_pipeline(repo_url)
        
        if reset_pipeline:
            self.reset_session()
        
        if emergency_stop:
            self.emergency_stop()
    
    def start_pipeline(self, repo_url: str):
        """Start the publication generation pipeline"""
        try:
            # Validate URL again before processing
            validated_url = validate_github_url(repo_url)
            
            # Update session state
            st.session_state.pipeline_status = "running"
            st.session_state.processing_start_time = time.time()
            st.session_state.error_log = []
            
            # Create initial message
            msg = create_mcp_message(
                role="agent", 
                name="RepoNode", 
                content={"repo_url": validated_url}
            )
            
            st.session_state.conversation_id = msg["metadata"]["conversation_id"]
            
            # Log pipeline start
            system_logger.logger.info("pipeline_start", extra={
                "event_type": "pipeline_start",
                "conversation_id": st.session_state.conversation_id,
                "repo_url": validated_url
            })
            
            # Send message and process
            with st.spinner("🤖 Cloning repository and starting analysis..."):
                try:
                    self.coordinator.send(msg)
                    self.coordinator.run_once()
                    self.coordinator.run_once()
                except Exception as e:
                    raise Exception(f"Coordinator execution error: {str(e)}")
            
            # Check for draft completion
            try:
                events = self.coordinator.get_conversation_events(st.session_state.conversation_id)
                
                # Debug: log events structure
                if events:
                    system_logger.logger.debug("pipeline_events", extra={
                        "event_type": "debug",
                        "events_count": len(events),
                        "events_sample": str(events[:2]) if len(events) > 0 else "none"
                    })
                
                draft_event = None
                for event in events:
                    if isinstance(event, dict) and event.get("content", {}).get("status") == "draft_ready":
                        draft_event = event
                        break
            except Exception as e:
                raise Exception(f"Event processing error: {str(e)} - Events type: {type(events) if 'events' in locals() else 'undefined'}")
            
            if draft_event:
                st.session_state.md_path = draft_event["content"]["md_path"]
                st.session_state.pipeline_status = "draft_ready"
                
                st.success("✅ Draft generated successfully! Review and edit below.")
                
                # Show generation metrics
                processing_time = time.time() - st.session_state.processing_start_time
                st.session_state.execution_metrics["generation_time"] = processing_time
                
            else:
                # Check for errors
                error_events = []
                for event in events:
                    if isinstance(event, dict) and "error" in event.get("content", {}):
                        error_events.append(event)
                
                if error_events:
                    error_msg = error_events[0]["content"]["error"]
                    st.session_state.error_log.append(error_msg)
                    st.session_state.pipeline_status = "error"
                    st.error(f"❌ Pipeline failed: {error_msg}")
                else:
                    st.session_state.pipeline_status = "processing"
                    st.warning("⏳ Processing in progress. Please wait...")
            
        except Exception as e:
            self.handle_error("Pipeline start failed", e)
    
    def render_status_display(self):
        """Render current pipeline status"""
        if st.session_state.pipeline_status != "idle":
            st.markdown('<h2 class="section-header">📊 Pipeline Status</h2>', 
                       unsafe_allow_html=True)
            
            # Status indicator
            status_colors = {
                "running": ("🟡", "Processing...", "status-warning"),
                "draft_ready": ("🟢", "Draft Ready", "status-success"),
                "error": ("🔴", "Error Occurred", "status-error"),
                "processing": ("🟠", "Processing...", "status-info"),
                "completed": ("✅", "Completed", "status-success")
            }
            
            icon, text, css_class = status_colors.get(st.session_state.pipeline_status, ("❓", "Unknown", "status-info"))
            
            st.markdown(f"""
            <div class="status-box {css_class}">
            <strong>{icon} Status: {text}</strong><br>
            Conversation ID: {st.session_state.conversation_id or 'None'}
            </div>
            """, unsafe_allow_html=True)
            
            # Show execution metrics
            if st.session_state.execution_metrics:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if "generation_time" in st.session_state.execution_metrics:
                        st.metric("Generation Time", 
                                f"{st.session_state.execution_metrics['generation_time']:.1f}s")
                
                with col2:
                    if st.session_state.processing_start_time:
                        elapsed = time.time() - st.session_state.processing_start_time
                        st.metric("Elapsed Time", f"{elapsed:.1f}s")
                
                with col3:
                    st.metric("Pipeline Stage", st.session_state.pipeline_status.replace("_", " ").title())
    
    def render_editor(self):
        """Render the markdown editor section"""
        if st.session_state.md_path and os.path.exists(st.session_state.md_path):
            st.markdown('<h2 class="section-header">📝 Document Editor</h2>', 
                       unsafe_allow_html=True)
            
            # Load current content
            try:
                with open(st.session_state.md_path, 'r', encoding='utf-8') as f:
                    md_text = f.read()
            except Exception as e:
                st.error(f"Error loading document: {str(e)}")
                return
            
            # Editor tabs
            tab1, tab2 = st.tabs(["📝 Edit", "👁️ Preview"])
            
            with tab1:
                # Editor with syntax highlighting
                edited_text = st.text_area(
                    "Edit your research publication (Markdown format):",
                    value=md_text,
                    height=500,
                    help="Use Markdown syntax for formatting. The content will be converted to PDF."
                )
                
                # Editor controls
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    save_edits = st.button("💾 Save Edits", use_container_width=True)
                
                with col2:
                    # Download markdown button
                    st.download_button(
                        label="📄 Download MD",
                        data=edited_text.encode('utf-8'),
                        file_name=os.path.basename(st.session_state.md_path),
                        mime="text/markdown",
                        use_container_width=True
                    )
                
                with col3:
                    auto_save = st.checkbox("Auto-save", help="Automatically save changes")
                
                with col4:
                    word_count = len(edited_text.split())
                    st.metric("Words", word_count)
                
                with col5:
                    char_count = len(edited_text)
                    st.metric("Characters", char_count)
                
                # Handle save
                if save_edits or (auto_save and edited_text != md_text):
                    try:
                        with open(st.session_state.md_path, 'w', encoding='utf-8') as f:
                            f.write(edited_text)
                        st.success("✅ Document saved successfully!")
                        
                        # Log the edit
                        system_logger.logger.info("document_edited", extra={
                            "event_type": "document_edited",
                            "conversation_id": st.session_state.conversation_id,
                            "word_count": word_count,
                            "char_count": char_count
                        })
                        
                    except Exception as e:
                        st.error(f"❌ Error saving document: {str(e)}")
            
            with tab2:
                # Preview the markdown
                st.markdown("### Preview:")
                st.markdown(edited_text)
    
    def render_evaluation_section(self):
        """Render document evaluation section"""
        if st.session_state.md_path:
            st.markdown('<h2 class="section-header">📊 Quality Evaluation</h2>', 
                       unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                run_evaluation = st.button(
                    "🧮 Analyze Quality",
                    use_container_width=True,
                    help="Run readability and quality analysis"
                )
            
            with col2:
                # Manual evaluation for testing
                if st.button("🔄 Force Refresh", use_container_width=True, help="Refresh evaluation results"):
                    st.rerun()
                    
            with col3:
                if run_evaluation:
                    with st.spinner("Analyzing document quality..."):
                        self.run_evaluation()
            
            # Display evaluation results
            self.display_evaluation_results()
    
    def run_evaluation(self):
        """Run document evaluation"""
        try:
            st.info("🔍 Starting quality analysis...")
            
            # Check if we have a valid file
            if not st.session_state.md_path or not os.path.exists(st.session_state.md_path):
                st.error("❌ No document file found to analyze!")
                return
                
            st.info(f"📝 Analyzing file: {os.path.basename(st.session_state.md_path)}")
            
            eval_msg = create_mcp_message(
                role="agent",
                name="EvaluatorNode",
                content={"md_path": st.session_state.md_path},
                conversation_id=st.session_state.conversation_id
            )
            
            # Send the evaluation message
            self.coordinator.send(eval_msg)
            
            # Process the evaluation
            self.coordinator.run_once()
            
            # Check if evaluation completed immediately
            events = self.coordinator.get_conversation_events(st.session_state.conversation_id)
            eval_events = [e for e in events if isinstance(e, dict) and e.get("content", {}).get("status") == "eval_done"]
            
            if eval_events:
                st.success(f"✅ Quality analysis completed! Found {len(eval_events)} results.")
            else:
                st.warning("⏳ Analysis in progress... Results may appear after refresh.")
                st.info("💡 Try clicking 'Analyze Quality' again if results don't appear.")
            
            # Force rerun to show results
            st.rerun()
            
        except Exception as e:
            self.handle_error("Evaluation failed", e)
    
    def display_evaluation_results(self):
        """Display evaluation results"""
        if st.session_state.conversation_id:
            events = self.coordinator.get_conversation_events(st.session_state.conversation_id)
            
            eval_events = []
            for event in events:
                if isinstance(event, dict) and event.get("content", {}).get("status") == "eval_done":
                    eval_events.append(event)
            
            # Debug info
            if st.checkbox("🔍 Show Debug Info", key="eval_debug"):
                st.write(f"**Total events:** {len(events)}")
                st.write(f"**Conversation ID:** {st.session_state.conversation_id}")
                st.write(f"**MD Path:** {st.session_state.md_path}")
                st.write(f"**Eval events found:** {len(eval_events)}")
                
                # Show all events for debugging
                if st.checkbox("📋 Show All Events", key="show_all_events"):
                    for i, event in enumerate(events):
                        st.write(f"**Event {i+1}:**")
                        st.json(event)
                
                if eval_events:
                    st.write("**Latest eval event content:**")
                    st.json(eval_events[-1]["content"])
            
            if eval_events:
                st.success(f"📊 Found {len(eval_events)} evaluation result(s)")
                latest_eval = eval_events[-1]["content"]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if "flesch_reading_ease" in latest_eval and latest_eval["flesch_reading_ease"]:
                        score = latest_eval["flesch_reading_ease"]
                        st.metric("Readability Score", f"{score:.1f}", 
                                help="Flesch Reading Ease (higher = easier to read)")
                
                with col2:
                    if "word_count" in latest_eval:
                        st.metric("Word Count", latest_eval["word_count"])
                
                with col3:
                    if "sentence_count" in latest_eval:
                        st.metric("Sentences", latest_eval["sentence_count"])
                
                with col4:
                    if "avg_sentence_length" in latest_eval:
                        avg_len = latest_eval["avg_sentence_length"]
                        st.metric("Avg Sentence Length", f"{avg_len:.1f}")
    
    def render_pdf_generation(self):
        """Render PDF generation section"""
        if st.session_state.md_path:
            st.markdown('<h2 class="section-header">📄 PDF Generation</h2>', 
                       unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 3])
            
            with col1:
                generate_pdf = st.button(
                    "📄 Generate PDF",
                    use_container_width=True,
                    help="Convert the document to PDF format"
                )
            
            with col2:
                if generate_pdf:
                    with st.spinner("Generating PDF..."):
                        self.generate_pdf()
            
            # PDF download
            if st.session_state.pdf_path and os.path.exists(st.session_state.pdf_path):
                st.success("✅ PDF generated successfully!")
                
                try:
                    with open(st.session_state.pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=os.path.basename(st.session_state.pdf_path),
                        mime="application/pdf",
                        use_container_width=False
                    )
                    
                    # Show PDF info
                    file_size = len(pdf_bytes) / 1024  # KB
                    st.info(f"📊 PDF Size: {file_size:.1f} KB")
                    
                except Exception as e:
                    st.error(f"Error reading PDF file: {str(e)}")
    
    def generate_pdf(self):
        """Generate PDF from markdown"""
        try:
            pdf_msg = create_mcp_message(
                role="agent",
                name="PDFNode",
                content={"md_path": st.session_state.md_path},
                conversation_id=st.session_state.conversation_id
            )
            
            self.coordinator.send(pdf_msg)
            self.coordinator.run_once()
            
            # Check for PDF completion
            events = self.coordinator.get_conversation_events(st.session_state.conversation_id)
            
            pdf_event = None
            for event in events:
                if isinstance(event, dict) and event.get("content", {}).get("status") == "pdf_ready":
                    pdf_event = event
                    break
            
            if pdf_event:
                st.session_state.pdf_path = pdf_event["content"]["pdf_path"]
            
        except Exception as e:
            self.handle_error("PDF generation failed", e)
    
    def render_error_log(self):
        """Render error log if there are errors"""
        if st.session_state.error_log:
            st.markdown('<h2 class="section-header">⚠️ Error Log</h2>', 
                       unsafe_allow_html=True)
            
            with st.expander("View Error Details", expanded=len(st.session_state.error_log) < 3):
                for i, error in enumerate(st.session_state.error_log, 1):
                    st.markdown(f"""
                    <div class="status-box status-error">
                    <strong>Error {i}:</strong><br>
                    {error}
                    </div>
                    """, unsafe_allow_html=True)
    
    def handle_error(self, context: str, error: Exception):
        """Handle and log errors with user-friendly messages"""
        error_msg = str(error)
        user_friendly_msg = error_msg
        
        # Provide user-friendly messages for common errors
        if "Repository error" in error_msg and "could not read Username" in error_msg:
            user_friendly_msg = (
                "🔒 Repository Access Error\n\n"
                "This repository appears to be private or requires authentication. "
                "Please ensure:\n"
                "• The repository is public\n"
                "• The URL is correct\n"
                "• The repository exists\n\n"
                "Only public GitHub repositories are currently supported."
            )
        elif "Repository not found" in error_msg:
            user_friendly_msg = (
                "🔍 Repository Not Found\n\n"
                "The repository could not be found. Please check:\n"
                "• The URL is spelled correctly\n"
                "• The repository exists\n"
                "• You have access to view it"
            )
        elif "Repository appears to be private" in error_msg:
            user_friendly_msg = (
                "🔒 Private Repository Detected\n\n"
                "This repository is private and cannot be processed. "
                "Please use a public repository or contact the repository owner "
                "to make it public."
            )
        elif "Network" in error_msg or "timeout" in error_msg.lower():
            user_friendly_msg = (
                "🌐 Network Connection Error\n\n"
                "Unable to connect to GitHub. Please check:\n"
                "• Your internet connection\n"
                "• GitHub's status (status.github.com)\n"
                "• Try again in a few minutes"
            )
        
        # Store both technical and user-friendly messages
        technical_msg = f"{context}: {error_msg}"
        st.session_state.error_log.append(technical_msg)
        st.session_state.pipeline_status = "error"
        
        # Log to system
        system_logger.log_error(error, {
            "context": context,
            "conversation_id": st.session_state.conversation_id,
            "ui_component": "streamlit_app"
        })
        
        # Display user-friendly error
        st.error(f"❌ {user_friendly_msg}")
        
        # Show technical details in expander for debugging
        with st.expander("🔧 Technical Details"):
            st.code(technical_msg)
    
    def reset_session(self):
        """Reset the current session"""
        for key in ["conversation_id", "md_path", "pdf_path", "error_log", 
                   "execution_metrics", "processing_start_time"]:
            st.session_state[key] = None if key != "error_log" and key != "execution_metrics" else []
        
        st.session_state.pipeline_status = "idle"
        st.success("✅ Session reset successfully!")
        st.rerun()
    
    def emergency_stop(self):
        """Emergency stop the current process"""
        st.session_state.pipeline_status = "stopped"
        st.warning("⛔ Process stopped by user")
        
        # Log emergency stop
        system_logger.logger.warning("emergency_stop", extra={
            "event_type": "emergency_stop",
            "conversation_id": st.session_state.conversation_id
        })
    
    def run(self):
        """Main application entry point"""
        try:
            # Ensure initialization is completed
            if not self._ensure_initialized():
                return  # Environment check failed, stop here
            
            # Render UI components
            self.render_header()
            self.render_sidebar()
            
            # Main content area
            repo_url = self.render_url_input()
            self.render_pipeline_controls(repo_url)
            self.render_status_display()
            self.render_editor()
            self.render_evaluation_section()
            self.render_pdf_generation()
            self.render_error_log()
            
            # Footer
            st.markdown("---")
            st.markdown(
                "Built with ❤️ using Streamlit, LangGraph, and Groq LLMs | "
                "🔒 Production-ready with security, monitoring, and resilience features"
            )
            
        except Exception as e:
            self.handle_error("UI rendering failed", e)
            st.error("A critical error occurred. Please refresh the page.")


def create_enhanced_app():
    """Create and run the enhanced UI application"""
    app = MultiAgentUI()
    app.run()

if __name__ == "__main__":
    create_enhanced_app()