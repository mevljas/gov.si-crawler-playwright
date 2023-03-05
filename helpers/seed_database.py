from sqlalchemy.orm import sessionmaker

from helpers.models import DataType, PageType


def seed_default(engine):
    # creating session
    Session = sessionmaker(bind=engine)
    session = Session()

    # add multiple objects at the same time
    session.add_all(
        [
            DataType(code='PDF'),
            DataType(code='DOC'),
            DataType(code='DOCX'),
            DataType(code='PPT'),
            DataType(code='PPTX'),
            PageType(code='HTML'),
            PageType(code='BINARY'),
            PageType(code='DUPLICATE'),
            PageType(code='FRONTIER    '),
        ]
    )
    session.commit()
