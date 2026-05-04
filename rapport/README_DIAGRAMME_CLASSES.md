@startuml
skinparam classAttributeIconSize 0
skinparam linetype ortho
hide empty members

' ==============================
' IDENTITE
' ==============================
abstract class Person {
  +id: UUID
  +email: String
  +full_name: String
  +getDisplayName(): String
}

class User {
  +status: String
  +isActive: Boolean
  +isVerified: Boolean
  +save(): void
}

class Admin {
  +adminLevel: String
  +createSection(): void
  +validateSection(): void
}

Person <|-- User
Person <|-- Admin

class UserProfile {
  +bio: Text
  +country: String
  +avatar: String
  +getProfile(): void
}

User "1" *-- "1" UserProfile : composition

class Friendship {
  +status: String
  +createdAt: DateTime
}

class Follow {
  +createdAt: DateTime
}

User "1" -- "0..*" Friendship
User "1" -- "0..*" Follow

' ==============================
' INSTITUTION
' ==============================
class Country {
  +name: String
  +code: String
}

class Specialty {
  +name: String
  +domain: String
}

class Institution {
  +name: String
  +type: String
  +validate(): void
}

Country "1" o-- "0..*" Institution : aggregation
Institution "*" -- "*" Specialty
User --> Institution

' ==============================
' PLATEFORME SECTION (BASE)
' ==============================
abstract class PlatformSection {
  +id: UUID
  +name: String
  +status: String
  +description: Text
  +createdAt: DateTime
  +publish(): void
  +archive(): void
  +getStats(): Map
}

Admin --> PlatformSection : manage

' ==============================
' SECTION : COMMUNITY
' ==============================
class CommunitySection {
  +membersCount: int
  +getMembers(): List
}

PlatformSection <|-- CommunitySection

' --- Feed ---
class FeedSection {
  +postsCount: int
  +getPosts(): List
}

CommunitySection "1" *-- "1" FeedSection

class Post {
  +title: String
  +content: Text
  +mediaUrl: String
  +likesCount: int
  +publish(): void
  +like(): void
}

class PostComment {
  +content: Text
  +createdAt: DateTime
  +reply(): void
}

class Question {
  +title: String
  +content: Text
  +isSolved: Boolean
  +ask(): void
}

class Answer {
  +content: Text
  +isAccepted: Boolean
  +vote(): void
}

User "1" -- "0..*" Post
FeedSection "1" o-- "0..*" Post : aggregation
Post "1" *-- "0..*" PostComment : composition
User --> Question
User --> Answer
Question "1" *-- "0..*" Answer : composition

' --- Forum ---
class ForumSection {
  +topicsCount: int
  +moderate(): void
}

CommunitySection "1" *-- "1" ForumSection

class Topic {
  +title: String
  +category: String
  +isPinned: Boolean
  +create(): void
}

class ForumChatRoom {
  +name: String
  +isOpen: Boolean
  +open(): void
}

class ForumMessage {
  +content: Text
  +createdAt: DateTime
  +send(): void
}

ForumSection "1" o-- "0..*" Topic : aggregation
Topic "1" *-- "0..*" ForumChatRoom : composition
ForumChatRoom "1" *-- "0..*" ForumMessage : composition

' --- Projects ---
class ProjectSection {
  +projectsCount: int
  +createProject(): void
}

CommunitySection "1" *-- "1" ProjectSection

class Project {
  +title: String
  +description: Text
  +status: String
  +startDate: Date
  +start(): void
  +close(): void
}

class ProjectMember {
  +role: String
  +joinedAt: DateTime
}

class ProjectChatRoom {
  +name: String
  +createdAt: DateTime
  +open(): void
}

class ProjectChatMessage {
  +content: Text
  +createdAt: DateTime
  +send(): void
}

class ProjectTask {
  +title: String
  +status: String
  +dueDate: Date
  +assign(): void
}

ProjectSection "1" o-- "0..*" Project : aggregation
Project "1" *-- "0..*" ProjectMember : composition
Project "1" *-- "1" ProjectChatRoom : composition
ProjectChatRoom "1" *-- "0..*" ProjectChatMessage : composition
Project "1" *-- "0..*" ProjectTask : composition
User --> Project

' ==============================
' SECTION : RESOURCES
' ==============================
class ResourcesSection {
  +resourcesCount: int
  +addResource(): void
  +filterByType(): List
}

PlatformSection <|-- ResourcesSection

abstract class ResourceBase {
  +id: UUID
  +title: String
  +description: Text
  +thumbnail: String
  +createdAt: DateTime
  +delete(): void
  +publish(): void
}

ResourcesSection "1" o-- "0..*" ResourceBase : aggregation

' --- Content (Articles, Thesis, Memoire) ---
class ArticleSection {
  +articlesCount: int
  +filter(): List
}

ResourceBase <|-- ArticleSection

class Article {
  +abstract: Text
  +keywords: String
  +doi: String
  +publishedDate: Date
  +read(): void
}

class Thesis {
  +university: String
  +supervisor: String
  +defenseDate: Date
  +grade: String
  +download(): void
}

class Memoire {
  +university: String
  +supervisor: String
  +year: int
  +download(): void
}

ArticleSection "1" o-- "0..*" Article : aggregation
ArticleSection "1" o-- "0..*" Thesis : aggregation
ArticleSection "1" o-- "0..*" Memoire : aggregation

' --- Courses ---
class CoursesSection {
  +coursesCount: int
  +filterByLevel(): List
}

ResourceBase <|-- CoursesSection

class Course {
  +price: float
  +level: String
  +duration: int
  +language: String
  +enroll(): void
}

class CourseModule {
  +title: String
  +order: int
  +duration: int
}

class CourseLesson {
  +title: String
  +videoUrl: String
  +content: Text
  +play(): void
}

CoursesSection "1" o-- "0..*" Course : aggregation
Course "1" *-- "0..*" CourseModule : composition
CourseModule "1" *-- "0..*" CourseLesson : composition

' --- Tools ---
class ToolsSection {
  +toolsCount: int
}

ResourceBase <|-- ToolsSection

class Tool {
  +version: String
  +category: String
  +downloadUrl: String
  +isFree: Boolean
  +download(): void
}

ToolsSection "1" o-- "0..*" Tool : aggregation

' --- Corpus ---
class CorpusSection {
  +corporaCount: int
}

ResourceBase <|-- CorpusSection

class Corpus {
  +size: int
  +format: String
  +language: String
  +download(): void
}

CorpusSection "1" o-- "0..*" Corpus : aggregation

' ==============================
' SECTION : EVENTS
' ==============================
class EventsSection {
  +eventsCount: int
  +getUpcoming(): List
}

PlatformSection <|-- EventsSection

class Event {
  +title: String
  +description: Text
  +startDate: DateTime
  +endDate: DateTime
  +location: String
  +isOnline: Boolean
  +capacity: int
  +schedule(): void
  +cancel(): void
}

class EventRegistration {
  +registeredAt: DateTime
  +status: String
  +confirm(): void
}

class Speaker {
  +name: String
  +bio: Text
  +organization: String
  +topic: String
}

EventsSection "1" o-- "0..*" Event : aggregation
Event "1" *-- "0..*" EventRegistration : composition
Event "1" *-- "0..*" Speaker : composition
User --> EventRegistration

' ==============================
' SECTION : NEWS
' ==============================
class NewsSection {
  +articlesCount: int
  +getLatest(): List
}

PlatformSection <|-- NewsSection

class News {
  +title: String
  +content: Text
  +source: String
  +publishedAt: DateTime
  +category: String
  +publish(): void
}

class NewsTag {
  +name: String
}

NewsSection "1" o-- "0..*" News : aggregation
News "*" -- "*" NewsTag

' ==============================
' SECTION : OPPORTUNITIES
' ==============================
class OpportunitiesSection {
  +opportunitiesCount: int
  +filterByType(): List
}

PlatformSection <|-- OpportunitiesSection

class Opportunity {
  +title: String
  +description: Text
  +type: String
  +deadline: Date
  +location: String
  +isRemote: Boolean
  +apply(): void
}

class OpportunityApplication {
  +appliedAt: DateTime
  +status: String
  +resume: String
  +submit(): void
}

OpportunitiesSection "1" o-- "0..*" Opportunity : aggregation
Opportunity "1" *-- "0..*" OpportunityApplication : composition
User --> OpportunityApplication

' ==============================
' SECTION : INSTITUTIONS
' ==============================
class InstitutionsSection {
  +institutionsCount: int
  +search(): List
}

PlatformSection <|-- InstitutionsSection
InstitutionsSection "1" o-- "0..*" Institution : aggregation

' ==============================
' ADMIN PANEL
' ==============================
class AdminPanel {
  +getDashboard(): Map
  +getStats(): Map
  +manageUsers(): void
  +moderateContent(): void
}

class AdminLog {
  +action: String
  +targetType: String
  +targetId: UUID
  +performedAt: DateTime
}

class AdminRole {
  +name: String
  +permissions: List
}

Admin "1" *-- "1" AdminPanel : composition
AdminPanel "1" *-- "0..*" AdminLog : composition
Admin "*" -- "*" AdminRole

' ==============================
' CHATBOT
' ==============================
class ChatbotSection {
  +isEnabled: Boolean
  +model: String
}

PlatformSection <|-- ChatbotSection

class ChatSession {
  +sessionId: UUID
  +startedAt: DateTime
  +context: Text
  +start(): void
  +end(): void
}

class ChatMessage {
  +content: Text
  +role: String
  +sentAt: DateTime
  +send(): void
}

class ChatFeedback {
  +rating: int
  +comment: Text
  +submittedAt: DateTime
  +submit(): void
}

ChatbotSection "1" o-- "0..*" ChatSession : aggregation
User --> ChatSession
ChatSession "1" *-- "0..*" ChatMessage : composition
ChatMessage "1" *-- "0..*" ChatFeedback : composition

@enduml