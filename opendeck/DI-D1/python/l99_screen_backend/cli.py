"""CLI commands for L99 Screen Backend."""

from __future__ import annotations

import argparse
import json
import sys
import time
import base64
from pathlib import Path
from typing import Optional

from .backend import ScreenBackend, ImageUpdateRequest
from .image_processor import ImageProcessor
from .layout import LayoutModel
from .mock_transport import MockScreenTransport
from .callback_handler import CallbackHandler, CallbackResult
from .callback_adapter import CallbackAdapter


def create_test_png() -> bytes:
    """Create a minimal valid PNG for testing."""
    from PIL import Image
    import io
    img = Image.new('RGB', (80, 120), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def create_test_data_url() -> str:
    """Create a test PNG data URL."""
    png_bytes = create_test_png()
    b64 = base64.b64encode(png_bytes).decode('ascii')
    return f"data:image/png;base64,{b64}"


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate backend compatibility."""
    backend = ScreenBackend()
    result = backend.validate_compatibility()
    
    print(json.dumps(result, indent=2))
    
    if result["compatible"]:
        print("\n[OK] All compatibility checks PASSED")
        return 0
    else:
        print("\n[FAIL] Some compatibility checks FAILED")
        return 1


def cmd_demo(args: argparse.Namespace) -> int:
    """Run deterministic demo with sample icon updates."""
    backend = ScreenBackend()
    device_id = "al-l99-0001"
    profile_id = "default"
    
    print(f"Running demo for device={device_id}, profile={profile_id}")
    print("=" * 60)
    
    # Create test images (different colors for each position)
    from PIL import Image
    import io
    
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (128, 128, 128), (255, 128, 0),
        (128, 0, 255), (0, 128, 255), (255, 0, 128), (0, 255, 128),
        (128, 255, 0), (255, 128, 128), (128, 128, 255), (200, 200, 200)
    ]
    
    data_urls = []
    for color in colors:
        img = Image.new('RGB', (80, 120), color=color)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        data_urls.append(f"data:image/png;base64,{b64}")
    
    # Update all 16 positions
    print("\n1. Setting images for all 16 positions...")
    for pos, data_url in enumerate(data_urls):
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=profile_id,
            position=pos,
            data_url=data_url,
            timestamp=time.time()
        )
        result = backend.process_image_update(request)
        status = "DUP" if result.duplicate_suppressed else "NEW"
        print(f"  Position {pos:2d}: {result.logical_state:7s} | {result.physical_status:18s} | SHA: {result.image_sha256[:16] if result.image_sha256 else 'none'}... [{status}]")
    
    # Try duplicate updates (should be suppressed)
    print("\n2. Sending duplicate updates (should be suppressed)...")
    for pos in [0, 5, 10]:
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=profile_id,
            position=pos,
            data_url=data_urls[pos],
            timestamp=time.time()
        )
        result = backend.process_image_update(request)
        status = "DUP" if result.duplicate_suppressed else "NEW"
        print(f"  Position {pos:2d}: {result.logical_state:7s} | {result.physical_status:18s} | duplicate={result.duplicate_suppressed} [{status}]")
    
    # Clear some positions
    print("\n3. Clearing positions 0, 1, 2...")
    for pos in [0, 1, 2]:
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=profile_id,
            position=pos,
            data_url=None,
            timestamp=time.time()
        )
        result = backend.process_image_update(request)
        print(f"  Position {pos:2d}: {result.logical_state:7s} | {result.physical_status:18s}")
    
    # Test profile isolation
    print("\n4. Testing profile isolation (new profile 'profile2')...")
    profile2 = "profile2"
    request = ImageUpdateRequest(
        device_id=device_id,
        profile_id=profile2,
        position=0,
        data_url=data_urls[0],
        timestamp=time.time()
    )
    result = backend.process_image_update(request)
    print(f"  Position 0 in profile2: {result.logical_state:7s} | SHA: {result.image_sha256[:16] if result.image_sha256 else 'none'}...")
    
    # Verify original profile unchanged
    state = backend.state_manager.get_state(device_id, profile_id, 0)
    print(f"  Position 0 in profile1 (original): {state.logical_state.value if state else 'unknown'} | SHA: {state.image_sha256[:16] if state and state.image_sha256 else 'none'}...")
    
    # Test reconnect restoration
    print("\n5. Testing reconnect restoration...")
    backend.mock_transport.disconnect()
    restored = backend.handle_reconnect(device_id, profile_id)
    print(f"  Restored {restored} images on reconnect")
    
    # Export transport trace
    trace_path = Path(args.output_dir) / "mock_transport_trace.json"
    backend.export_transport_trace(str(trace_path))
    print(f"\n6. Transport trace exported to: {trace_path}")
    
    # Export preview data
    preview = backend.get_preview_data(device_id, profile_id)
    preview_path = Path(args.output_dir) / "preview_data.json"
    with open(preview_path, 'w') as f:
        json.dump(preview, f, indent=2)
    print(f"   Preview data exported to: {preview_path}")
    
    # Export diagnostics
    diag = backend.get_diagnostics()
    diag_path = Path(args.output_dir) / "diagnostics.json"
    with open(diag_path, 'w') as f:
        json.dump(diag, f, indent=2)
    print(f"   Diagnostics exported to: {diag_path}")
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Run automated tests."""
    import pytest
    
    test_file = Path(__file__).parent.parent / "tests" / "test_screen_backend.py"
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return 1
    
    # Run pytest
    result = pytest.main([
        "-v",
        "--tb=short",
        str(test_file),
        "-x" if args.fail_fast else ""
    ])
    
    return result


def cmd_preview(args: argparse.Namespace) -> int:
    """Generate offline preview image."""
    from PIL import Image, ImageDraw, ImageFont
    
    backend = ScreenBackend()
    device_id = args.device_id or "al-l99-0001"
    profile_id = args.profile_id or "default"
    
    # Create some test images
    test_url = create_test_data_url()
    
    # Set a few images
    for pos in [0, 1, 5, 10, 15]:
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=profile_id,
            position=pos,
            data_url=test_url,
            timestamp=time.time()
        )
        backend.process_image_update(request)
    
    # Get preview data
    preview = backend.get_preview_data(device_id, profile_id)
    
    # Render preview
    img = Image.new('RGB', (preview['screen_width'], preview['screen_height']), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except:
        font = ImageFont.load_default()
    
    for btn in preview['buttons']:
        x, y = btn['x'], btn['y']
        w, h = btn['width'], btn['height']
        pos = btn['position']
        state = btn['logical_state']
        has_img = btn['has_image']
        
        # Draw cell border
        color = (100, 100, 100)
        if state == 'on':
            color = (0, 200, 0) if has_img else (200, 200, 0)
        elif state == 'error':
            color = (200, 0, 0)
        elif state == 'off':
            color = (100, 100, 100)
        
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=color, width=2)
        
        # Draw position number
        text = f"{pos}"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x + (w - tw) // 2, y + (h - th) // 2), text, fill=(200, 200, 200), font=font)
        
        # Draw state indicator
        state_text = state.upper()
        bbox = draw.textbbox((0, 0), state_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x + 2, y + h - th - 2), state_text, fill=color, font=font)
    
    # Draw warning
    warning = "PREVIEW ONLY - Overlaps stock Home Navigation"
    bbox = draw.textbbox((0, 0), warning, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((preview['screen_width'] // 2 - tw // 2, preview['screen_height'] - 20), warning, fill=(255, 100, 100), font=font)
    
    output_path = Path(args.output_dir) / "screen_preview.png"
    img.save(output_path)
    print(f"Preview saved to: {output_path}")
    
    return 0


def cmd_callback_demo(args: argparse.Namespace) -> int:
    """Run a callback-driven demo simulating genuine OpenDeck setImage callbacks."""
    backend = ScreenBackend()
    adapter = CallbackAdapter(backend=backend, profile_id="default")

    results = []

    def on_result(result: CallbackResult) -> None:
        results.append(result)

    adapter.set_result_callback(on_result)

    device_id = "al-l99-0001"

    # Create two distinct test images
    from PIL import Image
    import io
    import base64

    def make_data_url(color):
        img = Image.new('RGB', (80, 120), color=color)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:image/png;base64,{b64}"

    url_red = make_data_url((255, 0, 0))
    url_green = make_data_url((0, 255, 0))

    print(f"Callback demo for device={device_id}, profile={adapter.profile_id}")
    print("=" * 60)

    # 1. Valid set image at position 0
    print("\n1. Callback: set image pos=0 (red)")
    adapter.submit(device_id, 0, url_red)
    adapter.process_one(block=False)

    # 2. Duplicate set image at position 0 (should suppress)
    print("2. Callback: duplicate set image pos=0 (red)")
    adapter.submit(device_id, 0, url_red)
    adapter.process_one(block=False)

    # 3. Change icon at position 0 (green -> SHA changes)
    print("3. Callback: change icon pos=0 (green)")
    adapter.submit(device_id, 0, url_green)
    adapter.process_one(block=False)

    # 4. Clear position 1
    print("4. Callback: clear pos=1")
    adapter.submit(device_id, 1, None)
    adapter.process_one(block=False)

    # 5. Invalid device rejected
    print("5. Callback: invalid device (rejected)")
    adapter.submit("unknown-device", 0, url_red)
    adapter.process_one(block=False)

    # 6. Invalid position rejected
    print("6. Callback: invalid position 16 (rejected)")
    adapter.submit(device_id, 16, url_red)
    adapter.process_one(block=False)

    # 7. Clear all (None, None)
    print("7. Callback: clear all (None, None)")
    adapter.submit(device_id, None, None)
    adapter.process_one(block=False)

    # Print results
    print("\n--- Callback Results ---")
    for i, r in enumerate(results):
        br = r.backend_result
        if isinstance(br, list):
            print(f"  [{i}] clear_all accepted={r.accepted} count={len(br)}")
        elif br is None:
            print(f"  [{i}] REJECTED: {r.error}")
        else:
            print(f"  [{i}] pos={r.position} accepted={r.accepted} "
                  f"sha={br.image_sha256[:12] if br.image_sha256 else 'none'} "
                  f"dup={getattr(br, 'duplicate_suppressed', False)}")

    # Export traces
    backend.export_transport_trace(str(Path(args.output_dir) / "mock_transport_trace.json"))
    print(f"\nTransport trace exported to: {args.output_dir}\\mock_transport_trace.json")
    return 0


def cmd_callback_test(args: argparse.Namespace) -> int:
    """Run callback integration tests."""
    import pytest
    test_file = Path(__file__).parent.parent / "tests" / "test_screen_backend.py"
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return 1
    result = pytest.main([
        "-v",
        "--tb=short",
        str(test_file),
        "-x" if args.fail_fast else ""
    ])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="L99 Screen Backend - Offline screen-output for OpenDeck"
    )
    parser.add_argument(
        "--output-dir",
        default="C:\\temp\\aula-l99-controller\\opendeck\\OD2-B-R1\\output",
        help="Output directory for generated files"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate backend compatibility")
    subparsers.add_parser("demo", help="Run deterministic demo")
    cb_demo = subparsers.add_parser("callback-demo", help="Run callback-driven demo")
    cb_demo.set_defaults(func=cmd_callback_demo)
    subparsers.add_parser("callback-test", help="Run callback integration tests")
    preview_parser = subparsers.add_parser("preview", help="Generate offline preview image")
    preview_parser.add_argument("--device-id", default="al-l99-0001")
    preview_parser.add_argument("--profile-id", default="default")

    args = parser.parse_args()

    # Ensure output directory exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    commands = {
        "validate": cmd_validate,
        "demo": cmd_demo,
        "test": cmd_test,
        "callback-demo": cmd_callback_demo,
        "callback-test": cmd_callback_test,
        "preview": cmd_preview,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())