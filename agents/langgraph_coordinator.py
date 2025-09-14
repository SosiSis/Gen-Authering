# agents/langgraph_coordinator.py
from queue import Queue
import threading, time
from mcp import create_mcp_message, get_conversation_id

class LangGraphCoordinator:
    def __init__(self):
        self.msg_queue = Queue()
        self.nodes = {}  # name -> callable(msg, send)
        self.edges = {}  # source_node -> [target_nodes]
        self.consumers_log = []  # store conversation events (for UI)
        self.running = False

    def register_node(self, name: str, fn):
        self.nodes[name] = fn

    def add_edge(self, source: str, target: str):
        """Add an edge from source node to target node."""
        if source not in self.edges:
            self.edges[source] = []
        self.edges[source].append(target)

    def send(self, mcp_msg):
        # canonicalize minimal metadata
        if "metadata" not in mcp_msg:
            mcp_msg["metadata"] = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "conversation_id": None}
        self.msg_queue.put(mcp_msg)

    def _dispatch(self, mcp_msg):
        # If a node name is present as mcp_msg["name"], try call that node, otherwise call Coordinator
        target_name = mcp_msg.get("name")
        # If target node is of form "AnalyzerNode" -> call that node. If name corresponds to a node, route
        node_fn = self.nodes.get(target_name)
        # Also log
        self.consumers_log.append(mcp_msg)
        if node_fn:
            try:
                result = node_fn(mcp_msg, self.send)
                # If this node has outgoing edges, route the result to connected nodes
                if target_name in self.edges and result:
                    for next_node in self.edges[target_name]:
                        next_msg = create_mcp_message("node", next_node, result.get("content", {}))
                        self.send(next_msg)
            except Exception as e:
                print("Node error", target_name, e)
        else:
            # If no node matches, attempt default routing by 'content' hints:
            print("No node registered for", target_name)

    def run_once(self):
        """Process all messages currently in queue (blocking until queue empty)."""
        while not self.msg_queue.empty():
            msg = self.msg_queue.get()
            self._dispatch(msg)

    def get_conversation_events(self, conversation_id=None):
        if conversation_id is None:
            return list(self.consumers_log)
        else:
            return [m for m in self.consumers_log if m.get("metadata",{}).get("conversation_id")==conversation_id]
