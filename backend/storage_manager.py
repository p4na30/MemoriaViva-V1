"""Account configuration, SHA-256 PIN security, profile JSON management, and photo album assets."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.config import (
    ACCOUNT_CONFIG_PATH,
    DEMO_PROFILE_PATH,
    MEMORY_ALBUM_THEMES,
    MIN_SCREENSAVER_PHOTOS,
    PHOTOS_DIR,
    PROFILES_DIR,
    SAMPLE_ASSETS_DIR,
    ensure_data_directories,
)
from backend.database import DatabaseManager

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

THEME_PALETTES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]] = {
    "ferrocarril": ((34, 49, 63), (186, 132, 74), (244, 236, 224)),
    "musica_boleros": ((68, 36, 48), (212, 163, 115), (250, 243, 232)),
    "playa_manzanillo": ((18, 86, 108), (235, 152, 78), (252, 245, 232)),
    "familia_hogar": ((32, 78, 84), (199, 145, 92), (248, 243, 235)),
    "mascotas": ((44, 72, 54), (206, 154, 96), (249, 244, 235)),
}


def generate_link_code() -> str:
    """Generate a short human-friendly Telegram deep-link code like MV-4821."""
    digits = "".join(str(secrets.randbelow(10)) for _ in range(4))
    return f"MV-{digits}"


def hash_pin(pin: str, salt: Optional[str] = None) -> str:
    """Hash caregiver PIN with SHA-256 + random salt."""
    clean = str(pin).strip()
    use_salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256(f"{use_salt}:{clean}".encode("utf-8")).hexdigest()
    return f"sha256${use_salt}${digest}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    """Verify a caregiver PIN against its stored salted SHA-256 hash."""
    if not stored_hash or not pin:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "sha256":
        return False
    _, salt, expected = parts
    candidate = hashlib.sha256(f"{salt}:{str(pin).strip()}".encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, expected)


class StorageManager:
    """Manages account settings, biographical profiles (RAG-Lite), and family album photos."""

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        ensure_data_directories()
        self.db = db or DatabaseManager()
        if data_dir is not None:
            self.data_dir = Path(data_dir)
            self.profiles_dir = self.data_dir / "profiles"
            self.photos_dir = self.data_dir / "photos"
            self.account_path = self.data_dir / "account_config.json"
            self.profiles_dir.mkdir(parents=True, exist_ok=True)
            self.photos_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.data_dir = ACCOUNT_CONFIG_PATH.parent
            self.profiles_dir = PROFILES_DIR
            self.photos_dir = PHOTOS_DIR
            self.account_path = ACCOUNT_CONFIG_PATH

        self.sample_assets_dir = SAMPLE_ASSETS_DIR
        self._ensure_default_account()

    def _default_account(self) -> Dict[str, Any]:
        return {
            "is_registered": False,
            "kiosk_locked": False,
            "active_profile_id": "don_manuel",
            "is_demo_mode": True,
            "caregiver_name": "Laura González",
            "caregiver_username": "laura.gonzalez",
            "pin_hash": hash_pin("1234"),
            "rotation_interval_sec": 8,
            "theme_mode": "light",
            "voice_gender": "male",
            "telegram_link_code": generate_link_code(),
            "telegram_chat_id": "",
            "consent_caregiver_accepted": False,
            "consent_caregiver_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _ensure_default_account(self) -> None:
        if not self.account_path.exists():
            self.save_account_config(self._default_account())

    def load_account_config(self) -> Dict[str, Any]:
        self._ensure_default_account()
        try:
            data = json.loads(self.account_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = self._default_account()
            self.save_account_config(data)
        defaults = self._default_account()
        for k, v in defaults.items():
            data.setdefault(k, v)
        return data

    def save_account_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        config["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.account_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.account_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.account_path)
        return config

    def get_public_account_config(self) -> Dict[str, Any]:
        """Return account config without exposing pin_hash."""
        cfg = self.load_account_config()
        public = {k: v for k, v in cfg.items() if k != "pin_hash"}
        public["has_pin"] = bool(cfg.get("pin_hash"))
        return public

    # ------------------------------------------------------------------
    # Profiles & Biographical RAG-Lite
    # ------------------------------------------------------------------
    def _profile_path(self, profile_id: str) -> Path:
        if profile_id == "don_manuel":
            local_copy = self.profiles_dir / "don_manuel_runtime.json"
            if local_copy.exists():
                return local_copy
            return self.profiles_dir / "don_manuel_runtime.json"
        safe_id = "".join(c for c in profile_id if c.isalnum() or c in ("_", "-")) or "paciente"
        return self.profiles_dir / f"{safe_id}.json"

    def load_demo_seed_profile(self) -> Dict[str, Any]:
        return json.loads(DEMO_PROFILE_PATH.read_text(encoding="utf-8"))

    def load_profile(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        pid = profile_id or self.load_account_config().get("active_profile_id", "don_manuel")
        path = self._profile_path(pid)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        seed = self.load_demo_seed_profile()
        self.save_profile(seed, pid)
        return seed

    def save_profile(self, profile: Dict[str, Any], profile_id: Optional[str] = None) -> Dict[str, Any]:
        pid = profile_id or profile.get("paciente", {}).get("id") or "don_manuel"
        profile.setdefault("recuerdos_aprendidos", [])
        path = self._profile_path(pid)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return profile

    def reset_demo_profile(self) -> Dict[str, Any]:
        """Restore Don Manuel's clean seed profile (clearing learned facts from rehearsals)."""
        seed = copy.deepcopy(self.load_demo_seed_profile())
        seed["recuerdos_aprendidos"] = []
        return self.save_profile(seed, "don_manuel")

    def append_learned_facts(
        self, facts: List[str], profile_id: Optional[str] = None
    ) -> List[str]:
        """Persist newly extracted biographical facts into the patient's JSON profile (RAG-Lite)."""
        if not facts:
            return []
        profile = self.load_profile(profile_id)
        learned: List[str] = list(profile.get("recuerdos_aprendidos") or [])
        anchors: List[str] = list(profile.get("anclas_de_reminiscencia") or [])
        existing_lower = {f.strip().lower() for f in learned + anchors}

        added: List[str] = []
        for fact in facts:
            clean = str(fact).strip()
            if len(clean) < 6:
                continue
            if clean.lower() not in existing_lower:
                learned.append(clean)
                existing_lower.add(clean.lower())
                added.append(clean)

        if added:
            profile["recuerdos_aprendidos"] = learned[-30:]
            self.save_profile(profile, profile_id)
        return added

    # ------------------------------------------------------------------
    # Family Photo Album (10+ Sample Postcards + Custom Uploads)
    # ------------------------------------------------------------------
    def _load_sample_manifest(self) -> List[Dict[str, str]]:
        manifest_path = self.sample_assets_dir / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return [
            {
                "filename": f"{i:02d}_recuerdo_familiar.jpg",
                "theme": MEMORY_ALBUM_THEMES[(i - 1) % len(MEMORY_ALBUM_THEMES)],
                "title": f"Recuerdo Familiar #{i}",
                "caption": "Fotografía del álbum familiar de MemoriaViva RISE.",
            }
            for i in range(1, MIN_SCREENSAVER_PHOTOS + 1)
        ]

    @staticmethod
    def _render_pillow_postcard(
        dest_path: Path, title: str, caption: str, theme: str, index: int
    ) -> None:
        """Fallback programmatic editorial postcard generator via Pillow."""
        bg_rgb, accent_rgb, cream_rgb = THEME_PALETTES.get(
            theme, ((30, 64, 78), (200, 145, 90), (248, 244, 236))
        )
        width, height = 1280, 800
        img = Image.new("RGB", (width, height), bg_rgb)
        draw = ImageDraw.Draw(img)

        # Warm vintage gradient bands
        for y in range(height):
            ratio = y / height
            r = int(bg_rgb[0] * (1 - 0.35 * ratio) + accent_rgb[0] * (0.28 * ratio))
            g = int(bg_rgb[1] * (1 - 0.35 * ratio) + accent_rgb[1] * (0.28 * ratio))
            b = int(bg_rgb[2] * (1 - 0.35 * ratio) + accent_rgb[2] * (0.28 * ratio))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Subtle postcard frame & decorative warm vignette shapes
        draw.rounded_rectangle(
            [(48, 48), (width - 48, height - 48)],
            radius=28,
            outline=cream_rgb,
            width=4,
        )
        draw.ellipse(
            [(width - 340, 80), (width - 100, 320)],
            fill=(accent_rgb[0], accent_rgb[1], accent_rgb[2]),
        )
        draw.rounded_rectangle(
            [(88, height - 260), (width - 88, height - 88)],
            radius=20,
            fill=(15, 23, 32),
        )

        # Load best available TrueType font or default
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_tag = ImageFont.load_default()
        for font_candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ):
            if Path(font_candidate).exists():
                font_title = ImageFont.truetype(font_candidate, 44)
                font_tag = ImageFont.truetype(font_candidate, 22)
                break
        for font_candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ):
            if Path(font_candidate).exists():
                font_sub = ImageFont.truetype(font_candidate, 26)
                break

        tag_label = f"POSTAL {index:02d}  |  {theme.replace('_', ' ').upper()}"
        draw.text((112, 100), tag_label, fill=cream_rgb, font=font_tag)
        draw.text((120, height - 232), title[:48], fill=cream_rgb, font=font_title)

        # Simple 2-line wrap for caption
        words = caption.split()
        line1, line2 = [], []
        for w in words:
            if len(" ".join(line1 + [w])) <= 66:
                line1.append(w)
            elif len(" ".join(line2 + [w])) <= 66:
                line2.append(w)
        draw.text((120, height - 168), " ".join(line1), fill=(226, 232, 240), font=font_sub)
        if line2:
            draw.text((120, height - 130), " ".join(line2), fill=(203, 213, 225), font=font_sub)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest_path, format="JPEG", quality=88)

    def ensure_sample_photos(self, profile_id: str = "don_manuel") -> List[Dict[str, Any]]:
        """Populate at least 10 themed nostalgic postcards from AI sample_assets or Pillow fallback."""
        manifest = self._load_sample_manifest()
        self.photos_dir.mkdir(parents=True, exist_ok=True)

        for idx, item in enumerate(manifest, start=1):
            filename = item["filename"]
            dest = self.photos_dir / filename
            src = self.sample_assets_dir / filename
            if not dest.exists():
                if src.exists() and src.stat().st_size > 1024:
                    shutil.copy2(src, dest)
                else:
                    self._render_pillow_postcard(
                        dest,
                        title=item["title"],
                        caption=item["caption"],
                        theme=item["theme"],
                        index=idx,
                    )
            self.db.upsert_photo_metadata(
                filename=filename,
                profile_id=profile_id,
                title=item["title"],
                caption=item["caption"],
                theme=item["theme"],
                is_sample=True,
            )

        return self.list_photos(profile_id)

    def list_photos(self, profile_id: str = "don_manuel") -> List[Dict[str, Any]]:
        """Return ordered album photos with URL, title, caption, and memory_album_theme."""
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        meta_map = self.db.get_photo_metadata_map(profile_id)
        files = sorted(
            [
                p
                for p in self.photos_dir.iterdir()
                if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
            ],
            key=lambda p: p.name,
        )
        photos: List[Dict[str, Any]] = []
        for p in files:
            meta = meta_map.get(p.name)
            if not meta:
                meta = self.db.upsert_photo_metadata(
                    filename=p.name,
                    profile_id=profile_id,
                    title=p.stem.replace("_", " ").title(),
                    caption="Recuerdo familiar cargado en el álbum de MemoriaViva.",
                    theme="familia_hogar",
                    is_sample=False,
                )
            photos.append(
                {
                    "filename": p.name,
                    "url": f"/api/photos/file/{p.name}",
                    "title": meta["title"],
                    "caption": meta["caption"],
                    "theme": meta["theme"],
                    "is_sample": bool(meta.get("is_sample", False)),
                }
            )
        return photos

    def save_uploaded_photo(
        self,
        original_filename: str,
        raw_bytes: bytes,
        profile_id: str = "don_manuel",
        title: str = "",
        caption: str = "",
        theme: str = "familia_hogar",
    ) -> Dict[str, Any]:
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            ext = ".jpg"
        safe_stem = "".join(c for c in Path(original_filename).stem if c.isalnum() or c in ("_", "-"))[:32]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"custom_{stamp}_{safe_stem or 'foto'}{ext}"
        dest = self.photos_dir / filename
        self.photos_dir.mkdir(parents=True, exist_ok=True)

        # Validate & normalize image with Pillow to prevent corrupted uploads
        from io import BytesIO

        with Image.open(BytesIO(raw_bytes)) as im:
            im = im.convert("RGB")
            im.thumbnail((1600, 1200))
            im.save(dest, format="JPEG", quality=88)

        clean_theme = theme if theme in MEMORY_ALBUM_THEMES else "familia_hogar"
        meta = self.db.upsert_photo_metadata(
            filename=filename,
            profile_id=profile_id,
            title=title.strip() or safe_stem.replace("_", " ").title() or "Recuerdo Familiar",
            caption=caption.strip() or "Fotografía familiar agregada al álbum de reminiscencia.",
            theme=clean_theme,
            is_sample=False,
        )
        return {
            "filename": filename,
            "url": f"/api/photos/file/{filename}",
            "title": meta["title"],
            "caption": meta["caption"],
            "theme": meta["theme"],
            "is_sample": False,
        }

    def delete_photo(self, filename: str, profile_id: str = "don_manuel") -> bool:
        safe_name = Path(filename).name
        target = self.photos_dir / safe_name
        if not target.exists():
            return False
        target.unlink(missing_ok=True)
        self.db.delete_photo_metadata(safe_name)
        return True

    def find_photo_for_theme(
        self, theme: str, profile_id: str = "don_manuel", current_filename: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Select a matching photo for Bidirectional Visual Anchoring (Voice -> Photo)."""
        photos = self.list_photos(profile_id)
        if not photos:
            return None
        candidates = [p for p in photos if p["theme"] == theme]
        if not candidates:
            return photos[0]
        if current_filename and len(candidates) > 1:
            others = [p for p in candidates if p["filename"] != current_filename]
            if others:
                return others[0]
        return candidates[0]
