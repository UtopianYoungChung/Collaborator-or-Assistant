
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

def create_multipanel_pdf(assets_dir: Path, output_path: Path):
    tools = ['openai', 'copilot', 'devin', 'cursor', 'claude']
    filenames = [f"{tool}_state_machine.png" for tool in tools]
    
    fig, axes = plt.subplots(3, 2, figsize=(15, 20))
    axes = axes.flatten()
    
    for i, (tool, filename) in enumerate(zip(tools, filenames)):
        img_path = assets_dir / filename
        if img_path.exists():
            img = mpimg.imread(str(img_path))
            axes[i].imshow(img)
            axes[i].set_title(tool.capitalize(), fontsize=16, fontweight='bold')
        else:
            axes[i].text(0.5, 0.5, f"Missing: {filename}", ha='center', va='center')
        axes[i].axis('off')
    
    # Hide the 6th empty subplot
    axes[5].axis('off')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Generated: {output_path}")

def create_pipeline_pdf(output_path: Path):
    # This is a simplified professional diagram using matplotlib
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Define boxes
    boxes = [
        ("Layer 1: Raw Data\n(JSON Timelines)", (0.5, 0.9)),
        ("Layer 2: Streaming Iterator\n(Memory-Efficient)", (0.5, 0.75)),
        ("Layer 3: Workflow Analysis\n(5-Phase Lifecycle)", (0.5, 0.6)),
        ("Layer 4: Statistical Aggregation\n(Wilson CIs, Chi-Square)", (0.5, 0.45)),
        ("Layer 5: Output Generation\n(JSON, Markdown, PDF)", (0.5, 0.3))
    ]
    
    for text, pos in boxes:
        ax.annotate(text, pos, xytext=(pos[0], pos[1]),
                    bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=1.5),
                    ha="center", va="center", fontsize=12)
        
    # Draw arrows
    for i in range(len(boxes) - 1):
        x = boxes[i][1][0]
        y_start = boxes[i][1][1] - 0.04
        y_end = boxes[i+1][1][1] + 0.04
        ax.annotate("", xy=(x, y_end), xytext=(x, y_start),
                    arrowprops=dict(arrowstyle="->", lw=1.5, color="black"))
        
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Generated: {output_path}")

if __name__ == "__main__":
    base_dir = Path("d:/OneDrive - University of Toronto/Year 2026/AIWare")
    assets_dir = base_dir / "assets"
    
    create_multipanel_pdf(assets_dir, base_dir / "manuscript" / "state_machines_multipanel.pdf")
    create_pipeline_pdf(base_dir / "manuscript" / "data_pipeline_enhanced.pdf")
