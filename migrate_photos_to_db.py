# =====================================================================
# migrate_photos_to_db.py
# Script de migração única — Lê as fotos existentes na pasta
# UPLOADS_DIR, grava como BLOB no banco e apaga os arquivos.
#
# Uso:  python migrate_photos_to_db.py
# =====================================================================

import sys
import shutil
import mimetypes


def migrate():
    from app import create_app
    from app.extensions import db
    from app.models.visitor import Visitor
    from app.paths import UPLOADS_DIR

    app = create_app()

    with app.app_context():

        if not UPLOADS_DIR.is_dir():
            print(f"[INFO] Pasta de uploads não encontrada: {UPLOADS_DIR}")
            print("       Nada pra migrar.")
            return

        # ── Varre todas as subpastas (cada uma é um CPF) ─────────
        photo_files = []
        for cpf_folder in UPLOADS_DIR.iterdir():
            if not cpf_folder.is_dir():
                continue
            for file in cpf_folder.iterdir():
                if file.is_file() and file.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    photo_files.append((cpf_folder.name, file))

        if not photo_files:
            print("Nenhuma foto encontrada na pasta de uploads.")
            return

        print(f"Encontradas {len(photo_files)} foto(s) na pasta de uploads.")
        print(f"Pasta: {UPLOADS_DIR}")
        print("-" * 60)

        migrated = 0
        skipped  = 0
        errors   = 0
        files_to_delete = []

        for cpf, file_path in photo_files:

            # Busca visitante pelo CPF (nome da subpasta)
            visitor = db.session.query(Visitor).filter(
                Visitor.cpf == cpf
            ).one_or_none()

            if not visitor:
                print(f"  [SKIP] CPF {cpf} — visitante não encontrado no banco")
                skipped += 1
                continue

            # Pula se já tem foto no banco
            if visitor.photo_data and len(visitor.photo_data) > 100:
                print(f"  [SKIP] {cpf} — já tem foto no banco ({len(visitor.photo_data)} bytes)")
                skipped += 1
                files_to_delete.append(file_path)
                continue

            try:
                img_bytes = file_path.read_bytes()

                if len(img_bytes) < 100:
                    print(f"  [SKIP] {cpf} — arquivo muito pequeno ({len(img_bytes)} bytes)")
                    skipped += 1
                    continue

                mime, _ = mimetypes.guess_type(str(file_path))
                if not mime or not mime.startswith("image/"):
                    mime = "image/jpeg"

                visitor.photo_data     = img_bytes
                visitor.photo_mimetype = mime

                files_to_delete.append(file_path)
                migrated += 1

                size_kb = len(img_bytes) / 1024
                print(f"  [OK]   {cpf} — {file_path.name} ({size_kb:.1f} KB, {mime})")

            except Exception as e:
                print(f"  [ERRO] {cpf} — {e}")
                errors += 1

        # ── Commit no banco ──────────────────────────────────────────
        db.session.commit()
        print("-" * 60)

        # ── Apagar arquivos migrados ─────────────────────────────────
        deleted = 0
        for f in files_to_delete:
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                print(f"  [WARN] Não conseguiu apagar {f}: {e}")

        # ── Apagar subpastas vazias ──────────────────────────────────
        for cpf_folder in UPLOADS_DIR.iterdir():
            if cpf_folder.is_dir():
                try:
                    cpf_folder.rmdir()  # só remove se estiver vazia
                except OSError:
                    pass  # pasta ainda tem arquivos, ignora

        # ── Tenta remover a pasta uploads se ficou vazia ─────────────
        try:
            UPLOADS_DIR.rmdir()
            print(f"\n🗑️  Pasta '{UPLOADS_DIR}' removida (vazia).")
        except OSError:
            remaining = list(UPLOADS_DIR.rglob("*"))
            if remaining:
                print(f"\n⚠️  Pasta '{UPLOADS_DIR}' ainda tem {len(remaining)} arquivo(s).")

        # ── Resumo ───────────────────────────────────────────────────
        print("-" * 60)
        print("Migração concluída!")
        print(f"  ✅ Migrados para o banco: {migrated}")
        print(f"  🗑️  Arquivos apagados:    {deleted}")
        print(f"  ⏭️  Pulados:              {skipped}")
        print(f"  ❌ Erros:                 {errors}")


if __name__ == "__main__":
    migrate()
