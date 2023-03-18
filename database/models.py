from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, \
    LargeBinary, MetaData
from sqlalchemy.orm import relationship, declarative_base, Mapped

meta = MetaData(schema="crawldb")
Base = declarative_base(metadata=meta)



class DataType(Base):
    """
    Available values: PDF, DOC, DOCX, PPT, PPTX
    """
    __tablename__ = 'data_type'

    code = Column(String(20), primary_key=True, autoincrement=False)


class PageType(Base):
    """
    Available values: HTML, BINARY, DUPLICATE, FRONTIER
    """
    __tablename__ = 'page_type'

    code = Column(String(20), primary_key=True, autoincrement=False)


class Site(Base):
    __tablename__ = 'site'

    id = Column(Integer, primary_key=True)
    domain = Column(String(500))
    robots_content = Column(Text)
    sitemap_content = Column(Text)


class Page(Base):
    __tablename__ = 'page'

    id: Mapped[int] = Column(Integer, primary_key=True)
    site_id: Mapped[int] = Column(ForeignKey('site.id', ondelete='RESTRICT'), index=True)
    page_type_code: Mapped[String] = Column(ForeignKey('page_type.code', ondelete='RESTRICT'), index=True)
    url: Mapped[String] = Column(String(3000), unique=True)
    html_content: Mapped[String] = Column(Text)
    http_status_code: Mapped[int] = Column(Integer)
    accessed_time = Column(DateTime)

    page_type = relationship('PageType')
    site = relationship('Site')
    relationship(back_populates="parent")


class Image(Base):
    __tablename__ = 'image'

    id: Mapped[int] = Column(Integer, primary_key=True)
    page_id: Mapped[int] = Column(ForeignKey('page.id', ondelete='RESTRICT'), index=True)
    filename: Mapped[String] = Column(String(255))
    content_type: Mapped[String] = Column(String(50))
    data = Column(LargeBinary)
    accessed_time = Column(DateTime)

    page = relationship('Page')


class Link(Base):
    __tablename__ = 'link'

    from_page: Mapped[int] = Column(ForeignKey('page.id', ondelete='RESTRICT'), primary_key=True, nullable=False,
                       index=True)
    to_page: Mapped[int] = Column(ForeignKey('page.id', ondelete='RESTRICT'), primary_key=True, nullable=False, index=True)
    relationship(back_populates="children")


class PageData(Base):
    __tablename__ = 'page_data'

    id: Mapped[int] = Column(Integer, primary_key=True)
    page_id: Mapped[int] = Column(ForeignKey('page.id', ondelete='RESTRICT'), index=True)
    data_type_code: Mapped[String] = Column(ForeignKey('data_type.code', ondelete='RESTRICT'), index=True)
    data = Column(LargeBinary)

    data_type = relationship('DataType')
    page = relationship('Page')
