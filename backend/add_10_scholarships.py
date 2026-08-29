import uuid
from datetime import UTC, datetime, timedelta
import sys

from app.database import SessionLocal
from app.models import (
    Account,
    Organization,
    Scholarship,
    ScholarshipVersion,
    SourceDocument,
    KnowledgeChunk,
    ApplicationTemplate,
    OwnershipDomain,
    PublicationStatus,
    ScholarshipLifecycle
)

SEED_NAMESPACE = uuid.UUID("52b9b24a-9e5f-4e19-81b1-4da8245b9ae1")

def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)

def timestamp(month: int, day: int, hour: int = 9) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)

def main():
    session = SessionLocal()
    
    # Find central organization
    org = session.query(Organization).filter_by(slug="national-education-support-directorate-demo").first()
    if not org:
        print("Central organization not found.")
        sys.exit(1)
        
    print(f"Found org: {org.display_name} (ID: {org.id})")
    
    for i in range(1, 11):
        slug = f"central-demo-scholarship-{i}-2026"
        title = f"Central Demo Scholarship Programme {i}"
        
        scholarship_id = stable_id(f"scholarship:{slug}")
        version_id = stable_id(f"version:{slug}:1")
        
        # Find publisher account
        publisher = session.query(Account).filter_by(login_identifier="central.publisher@demo.scholarsaathi.local").first()
        publisher_id = publisher.id if publisher else org.id

        # Create Scholarship
        scholarship = session.query(Scholarship).filter_by(id=scholarship_id).first()
        if not scholarship:
            scholarship = Scholarship(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=scholarship_id,
                organization_id=org.id,
                slug=slug,
                lifecycle_status=ScholarshipLifecycle.ACTIVE,
                is_synthetic=True,
            )
            session.add(scholarship)
        
        # Create Scholarship Version
        version = session.query(ScholarshipVersion).filter_by(id=version_id).first()
        if not version:
            version = ScholarshipVersion(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=version_id,
                scholarship_id=scholarship_id,
                organization_id=org.id,
                version_number=1,
                publication_status=PublicationStatus.PUBLISHED,
                knowledge_summary="Synthetic eligibility requirements.",
                title=title,
                summary=f"Synthetic demo scholarship {i} for central government.",
                academic_year="2026-27",
                scope="NATIONAL",
                applicable_state_codes=["ALL"],
                education_levels=["UNDERGRADUATE"],
                course_families=["BTECH", "BE", "BCA", "BSC"],
                category_tags=["MERIT", "INCOME"],
                benefit_amount_min=10000 * i,
                benefit_amount_max=15000 * i,
                benefit_summary=f"Up to ₹{15000 * i} annual academic support.",
                application_opens_at=timestamp(8, 1),
                application_deadline_at=timestamp(11, 30, 23),
                official_source_url=f"https://provider.gov.in/demo/{slug}",
                provider_helpdesk_url="https://provider.gov.in/help",
                last_provider_confirmed_at=timestamp(8, 20),
                created_by=publisher_id,
                published_by=publisher_id,
                published_at=timestamp(8, 20),
            )
            session.add(version)
            session.flush()

        # Create Application Template
        template_id = stable_id(f"application-template:{slug}")
        template = session.query(ApplicationTemplate).filter_by(id=template_id).first()
        if not template:
            template = ApplicationTemplate(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=template_id,
                organization_id=org.id,
                scholarship_version_id=version_id,
                template_version=1,
                status="OWNER_CONFIRMED",
                created_by=publisher_id,
            )
            session.add(template)
            
        # Create Source Document
        source_id = stable_id(f"source-document:{slug}:guidelines")
        source = session.query(SourceDocument).filter_by(id=source_id).first()
        if not source:
            source = SourceDocument(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=source_id,
                organization_id=org.id,
                scholarship_version_id=version_id,
                display_name=f"{title} — Synthetic Guidelines",
                source_kind="PROVIDER_GUIDELINE",
                content_type="text/plain",
                size_bytes=100,
                storage_key=f"synthetic/{slug}/guidelines.txt",
                source_url=f"https://provider.gov.in/demo/{slug}/guidelines",
                checksum_sha256="mock_hash_12345",
                extracted_text="Applicants must be enrolled in an undergraduate programme. The income ceiling is ₹8,00,000.",
                usage_rights_confirmed_at=timestamp(8, 19),
                confirmation_status="OWNER_CONFIRMED",
                uploaded_by=publisher_id,
            )
            session.add(source)
            session.flush()

        # Create Knowledge Chunk
        chunk_id = stable_id(f"chunk:{slug}:eligibility")
        chunk = session.query(KnowledgeChunk).filter_by(id=chunk_id).first()
        if not chunk:
            chunk = KnowledgeChunk(
                domain=OwnershipDomain.CENTRAL_GOVERNMENT,
                id=chunk_id,
                scholarship_version_id=version_id,
                organization_id=org.id,
                source_document_id=source_id,
                ordinal=1,
                page_number=1,
                section_title="Eligibility",
                provider_text=f"Applicants must be enrolled in an undergraduate programme. The income ceiling is ₹8,00,000.",
                confirmation_status="OWNER_CONFIRMED",
            )
            session.add(chunk)
            
    try:
        session.commit()
        print("Successfully added 10 scholarships.")
    except Exception as e:
        session.rollback()
        print(f"Error adding scholarships: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
