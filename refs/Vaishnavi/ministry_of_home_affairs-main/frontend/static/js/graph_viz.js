/**
 * Interactive Force-Directed Canvas Graph Visualizer
 * Ultra-smooth physics simulation, multi-relational edge rendering,
 * ego-expansion, cluster coloring, and shortest-path route highlighting.
 */

class NetworkGraphVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");

    this.nodes = [];
    this.edges = [];
    this.nodeMap = new Map();

    // Transform & Camera View
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.draggedNode = null;
    this.hoveredNode = null;
    this.selectedNode = null;
    this.highlightPath = null; // Node IDs in shortest path

    // Rendering Modes
    this.colorByCommunity = false;
    this.filterLabel = "";

    // Simulation settings
    this.isRunning = true;
    this.alpha = 1.0;
    this.alphaMin = 0.001;
    this.alphaDecay = 0.022;

    this.initEvents();
    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth;
    this.canvas.height = parent.clientHeight;
    if (this.panX === 0 && this.panY === 0) {
      this.panX = this.canvas.width / 2;
      this.panY = this.canvas.height / 2;
    }
    this.requestRender();
  }

  setData(nodesData, edgesData) {
    this.nodeMap.clear();
    const width = this.canvas.width;
    const height = this.canvas.height;

    // Initialize node physics properties
    this.nodes = nodesData.map((d, i) => {
      const angle = (i / nodesData.length) * 2 * Math.PI;
      const radius = 100 + Math.random() * 220;
      const node = {
        ...d,
        x: d.x !== undefined ? d.x : Math.cos(angle) * radius,
        y: d.y !== undefined ? d.y : Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        radius: this.getNodeRadius(d),
        color: this.getNodeColor(d)
      };
      this.nodeMap.set(node.id, node);
      return node;
    });

    this.edges = edgesData.map(e => ({
      ...e,
      sourceNode: this.nodeMap.get(e.source),
      targetNode: this.nodeMap.get(e.target)
    })).filter(e => e.sourceNode && e.targetNode);

    this.alpha = 1.0;
    this.restartSimulation();
  }

  getNodeRadius(node) {
    if (node.label === "Person") {
      const risk = node.risk_score || 0;
      return 12 + Math.min(risk / 8, 14);
    }
    if (node.label === "Case") return 18;
    if (node.label === "Organization") return 16;
    return 11;
  }

  getNodeColor(node) {
    if (this.colorByCommunity && node.community_color) {
      return node.community_color;
    }

    switch (node.label) {
      case "Person":
        const risk = node.risk_score || 0;
        if (risk >= 70) return "#EF4444"; // Critical Red
        if (risk >= 45) return "#F59E0B"; // High Amber
        return "#38BDF8"; // Cyan
      case "Case":
        return "#6366F1"; // Indigo
      case "Organization":
        return "#EC4899"; // Pink
      case "Location":
        return "#06B6D4"; // Teal
      case "Vehicle":
        return "#FBBF24"; // Amber
      case "FinancialAccount":
        return "#8B5CF6"; // Purple
      case "CommunicationRecord":
        return "#10B981"; // Emerald
      default:
        return "#94A3B8";
    }
  }

  updateColors() {
    this.nodes.forEach(n => {
      n.color = this.getNodeColor(n);
    });
    this.requestRender();
  }

  toggleCommunityColoring() {
    this.colorByCommunity = !this.colorByCommunity;
    this.updateColors();
  }

  initEvents() {
    let startX = 0, startY = 0;
    let isPanning = false;

    this.canvas.addEventListener("mousedown", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const worldPos = this.screenToWorld(mouseX, mouseY);

      const clickedNode = this.findNodeAt(worldPos.x, worldPos.y);
      if (clickedNode) {
        this.draggedNode = clickedNode;
        this.selectedNode = clickedNode;
        this.alpha = 0.5;
        this.restartSimulation();
        if (window.App && window.App.onNodeSelected) {
          window.App.onNodeSelected(clickedNode);
        }
      } else {
        isPanning = true;
        startX = mouseX - this.panX;
        startY = mouseY - this.panY;
      }
    });

    window.addEventListener("mousemove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.draggedNode) {
        const worldPos = this.screenToWorld(mouseX, mouseY);
        this.draggedNode.x = worldPos.x;
        this.draggedNode.y = worldPos.y;
        this.draggedNode.vx = 0;
        this.draggedNode.vy = 0;
        this.alpha = Math.max(this.alpha, 0.2);
        this.restartSimulation();
      } else if (isPanning) {
        this.panX = mouseX - startX;
        this.panY = mouseY - startY;
        this.requestRender();
      } else {
        const worldPos = this.screenToWorld(mouseX, mouseY);
        const hovered = this.findNodeAt(worldPos.x, worldPos.y);
        if (hovered !== this.hoveredNode) {
          this.hoveredNode = hovered;
          this.canvas.style.cursor = hovered ? "pointer" : "default";
          this.requestRender();
        }
      }
    });

    window.addEventListener("mouseup", () => {
      this.draggedNode = null;
      isPanning = false;
    });

    this.canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.88;
      const newScale = Math.min(Math.max(this.scale * zoomFactor, 0.15), 5.0);

      // Zoom towards mouse position
      this.panX = mouseX - (mouseX - this.panX) * (newScale / this.scale);
      this.panY = mouseY - (mouseY - this.panY) * (newScale / this.scale);
      this.scale = newScale;

      this.requestRender();
    });
  }

  screenToWorld(sx, sy) {
    return {
      x: (sx - this.panX) / this.scale,
      y: (sy - this.panY) / this.scale
    };
  }

  findNodeAt(wx, wy) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      const dx = wx - n.x;
      const dy = wy - n.y;
      if (dx * dx + dy * dy <= (n.radius + 6) * (n.radius + 6)) {
        return n;
      }
    }
    return null;
  }

  highlightPathRoute(nodeIds) {
    this.highlightPath = new Set(nodeIds);
    this.requestRender();
  }

  clearHighlight() {
    this.highlightPath = null;
    this.requestRender();
  }

  restartSimulation() {
    if (!this.isRunning) {
      this.isRunning = true;
      requestAnimationFrame(() => this.tick());
    }
  }

  tick() {
    if (this.alpha < this.alphaMin && !this.draggedNode) {
      this.isRunning = false;
      this.render();
      return;
    }

    // Force Physics Simulation
    const kRepel = 2400 * this.alpha;
    const kSpring = 0.045;
    const springLen = 95;
    const centerAttract = 0.008;

    // 1. Repulsion between all node pairs
    for (let i = 0; i < this.nodes.length; i++) {
      const n1 = this.nodes[i];
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n2 = this.nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const distSq = dx * dx + dy * dy + 100;
        const dist = Math.sqrt(distSq);
        const force = kRepel / distSq;

        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        n1.vx -= fx;
        n1.vy -= fy;
        n2.vx += fx;
        n2.vy += fy;
      }
    }

    // 2. Spring Attraction along Edges
    for (let i = 0; i < this.edges.length; i++) {
      const e = this.edges[i];
      const src = e.sourceNode;
      const dst = e.targetNode;
      const dx = dst.x - src.x;
      const dy = dst.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - springLen) * kSpring * this.alpha;

      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      src.vx += fx;
      src.vy += fy;
      dst.vx -= fx;
      dst.vy -= fy;
    }

    // 3. Center Attraction & Damping
    for (let i = 0; i < this.nodes.length; i++) {
      const n = this.nodes[i];
      if (n === this.draggedNode) continue;

      n.vx -= n.x * centerAttract * this.alpha;
      n.vy -= n.y * centerAttract * this.alpha;

      n.vx *= 0.65;
      n.vy *= 0.65;

      n.x += n.vx;
      n.y += n.vy;
    }

    this.alpha *= (1 - this.alphaDecay);
    this.render();

    requestAnimationFrame(() => this.tick());
  }

  requestRender() {
    if (!this.isRunning) {
      requestAnimationFrame(() => this.render());
    }
  }

  render() {
    const ctx = this.ctx;
    const width = this.canvas.width;
    const height = this.canvas.height;

    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(this.panX, this.panY);
    ctx.scale(this.scale, this.scale);

    // 1. Draw Edges
    for (let i = 0; i < this.edges.length; i++) {
      const e = this.edges[i];
      const src = e.sourceNode;
      const dst = e.targetNode;

      const isPathEdge = this.highlightPath && this.highlightPath.has(src.id) && this.highlightPath.has(dst.id);
      const isSelectedEdge = this.selectedNode && (src.id === this.selectedNode.id || dst.id === this.selectedNode.id);

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(dst.x, dst.y);

      if (isPathEdge) {
        ctx.strokeStyle = "#F59E0B";
        ctx.lineWidth = 3.5;
        ctx.shadowColor = "#F59E0B";
        ctx.shadowBlur = 10;
      } else if (isSelectedEdge) {
        ctx.strokeStyle = "#38BDF8";
        ctx.lineWidth = 2.2;
        ctx.shadowBlur = 0;
      } else {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
        ctx.lineWidth = 1.0;
        ctx.shadowBlur = 0;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw Edge Relation Label if Zoomed in
      if (this.scale > 0.8 || isPathEdge || isSelectedEdge) {
        const midX = (src.x + dst.x) / 2;
        const midY = (src.y + dst.y) / 2;
        ctx.font = "9px 'Inter', sans-serif";
        ctx.fillStyle = isPathEdge ? "#FCD34D" : (isSelectedEdge ? "#7DD3FC" : "rgba(148, 163, 184, 0.6)");
        ctx.textAlign = "center";
        ctx.fillText(e.relation_type || "", midX, midY - 3);
      }
    }

    // 2. Draw Nodes
    for (let i = 0; i < this.nodes.length; i++) {
      const n = this.nodes[i];
      const isSelected = this.selectedNode && this.selectedNode.id === n.id;
      const isHovered = this.hoveredNode && this.hoveredNode.id === n.id;
      const isPathNode = this.highlightPath && this.highlightPath.has(n.id);

      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);

      ctx.fillStyle = n.color;
      if (isPathNode) {
        ctx.shadowColor = "#F59E0B";
        ctx.shadowBlur = 18;
      } else if (isSelected || isHovered) {
        ctx.shadowColor = n.color;
        ctx.shadowBlur = 16;
      } else {
        ctx.shadowBlur = 0;
      }

      ctx.fill();
      ctx.shadowBlur = 0;

      // Outer Border
      ctx.lineWidth = isSelected ? 3.5 : (isHovered || isPathNode ? 2.5 : 1.5);
      ctx.strokeStyle = isSelected ? "#FFFFFF" : (isPathNode ? "#FCD34D" : "rgba(255, 255, 255, 0.4)");
      ctx.stroke();

      // Node Label Text
      ctx.font = isSelected ? "bold 12px 'Inter', sans-serif" : "10px 'Inter', sans-serif";
      ctx.fillStyle = isSelected ? "#FFFFFF" : "#CBD5E1";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(n.name, n.x, n.y + n.radius + 4);
    }

    ctx.restore();
  }

  centerOnNode(nodeId) {
    const node = this.nodeMap.get(nodeId);
    if (!node) return;

    this.selectedNode = node;
    this.panX = this.canvas.width / 2 - node.x * this.scale;
    this.panY = this.canvas.height / 2 - node.y * this.scale;
    this.requestRender();
  }
}

window.NetworkGraphVisualizer = NetworkGraphVisualizer;
