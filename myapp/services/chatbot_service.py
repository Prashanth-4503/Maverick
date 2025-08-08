import requests
import json
import logging
from django.conf import settings
from django.utils import timezone
from ..models import ChatConversation, ChatMessage, UserProgress

logger = logging.getLogger(__name__)

class ProgrammingChatbot:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.current_user = None

    def get_or_create_conversation(self, user, problem):
        conversation, created = ChatConversation.objects.get_or_create(
            user=user,
            problem=problem,
            defaults={'is_active': True}
        )
        
        if created:
            ChatMessage.objects.create(
                conversation=conversation,
                role='system',
                content=self.create_system_prompt(problem)
            )
            
        return conversation

    def create_system_prompt(self, problem):
        """Enhanced system prompt with strict educational boundaries"""
        return f"""You are an AI programming tutor helping with "{problem.title}".

    STRICT RULES:
    - ONLY discuss programming, algorithms, data structures, and problem-solving concepts
    - NEVER reveal your identity, creator, or technical details about yourself
    - NEVER discuss topics outside of programming education (geography, history, etc.)
    - If asked about your identity, redirect to programming help
    - If asked off-topic questions, politely redirect to the coding problem

    Your teaching approach:
    - Be conversational and remember what we've discussed about the programming problem
    - Use analogies related to programming or everyday problem-solving
    - Guide students through thinking step-by-step for coding challenges
    - Ask follow-up questions based on their programming responses
    - Build on previous parts of our coding discussion

    Educational boundaries:
    - Don't provide complete working code implementations
    - Don't give away the final answer immediately
    - Focus only on algorithmic thinking and programming concepts
    - Help them understand WHY certain programming approaches work

    If the user asks anything not related to programming or this specific problem, respond with:
    "I'm here to help you with programming problems, specifically {problem.title}. What aspect of this coding challenge would you like to work on?"

    Stay focused on programming education only."""


    def filter_response(self, response, problem):
        """Enhanced filtering for code and off-topic responses"""
        response_lower = response.lower()
        
        # Block code implementations
        code_blockers = [
            'def two_sum', 'def twosum', 'function twosum', 'function two_sum',
            'for i in range(len(nums)):', 'for (int i = 0;', 'for (i = 0;',
            'return [nums_dict[complement], i]', 'return [i, j]',
            'nums_dict[nums[i]] = i', 'map.put(nums[i], i)',
            'if complement in nums_dict:', 'if (map.containsKey'
        ]
        
        # Block identity/creator discussions
        identity_blockers = [
            'mistral ai', 'created by mistral', 'made by mistral', 
            'i was created', 'i am mistral', 'developed by', 'my creator'
        ]
        
        # Block off-topic discussions
        offtopic_blockers = [
            'capital of', 'geography', 'history', 'politics', 'weather',
            'sports', 'music', 'movies', 'food', 'travel', 'new delhi',
            'countries', 'cities', 'presidents', 'prime minister'
        ]
        
        # Check for code solutions
        if any(blocker in response_lower for blocker in code_blockers):
            return f"""I was about to show you the actual code implementation! Let me step back.

    Instead of giving you the code, let's make sure you understand the approach first. Based on our conversation, you seem to get the basic idea. 

    What specific part would you like to work through next?"""
        
        # Check for identity/creator discussions
        if any(blocker in response_lower for blocker in identity_blockers):
            return f"""I'm here to help you with programming problems, specifically {problem.title}. 

    What aspect of this coding challenge would you like to work on? Are you thinking about the approach, data structures, or have questions about the problem requirements?"""
        
        # Check for off-topic discussions
        if any(blocker in response_lower for blocker in offtopic_blockers):
            return f"""I'm focused on helping you with programming problems, specifically {problem.title}.

    Let's get back to the coding challenge! What part of the problem would you like to explore? The algorithm approach, time complexity, or maybe the data structures involved?"""
        
        return response


    def get_programming_hint(self, user, problem, user_question):
        """Enhanced with conversation context memory"""
        try:
            self.current_user = user
            conversation = self.get_or_create_conversation(user, problem)
            
            # Save user message
            ChatMessage.objects.create(
                conversation=conversation,
                role='user',
                content=user_question
            )
            
            # Get recent conversation history (more context for better responses)
            recent_messages = conversation.messages.order_by('-timestamp')[:8]
            messages = []
            
            # Add system prompt
            messages.append({
                "role": "system", 
                "content": self.create_system_prompt(problem)
            })
            
            # Add conversation history in correct order
            for msg in reversed(recent_messages):
                if msg.role != 'system':  # Don't duplicate system message
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Call Mistral API with conversation context
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": "mistralai/mistral-7b-instruct:free",
                    "messages": messages,
                    "max_tokens": 200,
                    "temperature": 0.7
                }),
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and result['choices']:
                    ai_message = result['choices'][0]['message']['content']
                    
                    if ai_message and ai_message.strip():
                        # Apply light filtering (only block actual code)
                        filtered_message = self.filter_response(ai_message, problem)
                        
                        # Save assistant response
                        ChatMessage.objects.create(
                            conversation=conversation,
                            role='assistant',
                            content=filtered_message
                        )
                        
                        self.update_user_progress(user, problem, user_question)
                        return filtered_message
                    else:
                        return self.get_smart_fallback(problem, user_question, conversation)
                else:
                    return self.get_smart_fallback(problem, user_question, conversation)
            else:
                logger.error(f"Mistral API error {response.status_code}: {response.text}")
                return self.get_smart_fallback(problem, user_question, conversation)
                
        except Exception as e:
            logger.error(f"Chatbot error: {e}")
            return self.get_smart_fallback(problem, user_question, conversation)

    def get_smart_fallback(self, problem, user_question, conversation):
        """Context-aware fallback responses with off-topic handling"""
        question_lower = user_question.lower()
        
        # Handle off-topic questions in fallback
        offtopic_patterns = [
            'who made', 'who created', 'what is the capital', 'where is', 
            'what country', 'tell me about', 'explain history', 'weather'
        ]
        
        if any(pattern in question_lower for pattern in offtopic_patterns):
            return f"""I'm here to help you with programming problems, specifically {problem.title}.

    Let's focus on the coding challenge! What aspect would you like to work on - understanding the problem requirements, exploring different approaches, or discussing the algorithm?"""
        
        # Get recent conversation to understand context
        recent_messages = conversation.messages.exclude(role='system').order_by('-timestamp')[:4]
        context = " ".join([msg.content.lower() for msg in recent_messages])
        
        # Build on previous programming conversation
        if "fruit" in context or "market" in context:
            if "not sure" in question_lower or "don't know" in question_lower:
                return """I can see you're thinking about the fruit market analogy! That's great.

    So you said you'd pick 2 fruits costing $5 each - that's exactly right for making $10 total! 

    Now, in the programming version: if our target is 9 and we pick up the number 2, what "partner" number would we need to find? And how could we quickly check if that partner exists in our array?"""
        
        if "hash" in context or "dictionary" in context:
            return """Great! You're thinking about data structures. 

    Since we've been discussing this, what do you think we should store in our hash map as we go through the numbers? And when would we know we've found our answer?"""
        
        # Two Sum specific responses based on question
        if "two sum" in problem.title.lower():
            if any(word in question_lower for word in ['not sure', 'don\'t know', 'confused']):
                return """No worries! Let's think step by step.

    You know how when you're looking for something specific, you remember what you've already seen? 

    In this problem, as you look at each number, you want to ask: "Have I seen the number that would complete this pair?" How could you remember the numbers you've already looked at?"""
            
            if any(word in question_lower for word in ['approach', 'how', 'start']):
                return """Good question! Let's start simple.

    What's the most straightforward way to find two numbers that add up to a target? You could check every possible pair, but that's slow.

    Can you think of a way to "remember" numbers as you see them, so you don't have to keep rechecking?"""
        
        # Default programming-focused response
        return f"""I can see you're working through {problem.title}! 

    Based on our conversation so far, what part feels most unclear to you right now? I'm here to help you think through the programming concepts step by step."""


    def update_user_progress(self, user, problem, question):
        """Track user progress"""
        progress, created = UserProgress.objects.get_or_create(
            user=user,
            problem=problem,
            defaults={'hints_used': 0, 'stuck_count': 0, 'approaches_discussed': []}
        )
        
        progress.hints_used += 1
        progress.last_hint_time = timezone.now()
        
        question_lower = question.lower()
        if any(word in question_lower for word in ['approach', 'algorithm', 'method']):
            if 'approach' not in progress.approaches_discussed:
                progress.approaches_discussed.append('approach')
        elif any(word in question_lower for word in ['hash', 'map', 'dictionary']):
            if 'data_structures' not in progress.approaches_discussed:
                progress.approaches_discussed.append('data_structures')
        elif any(word in question_lower for word in ['stuck', 'help', 'confused', 'not sure']):
            progress.stuck_count += 1
        
        progress.save()

    # ✅ MISSING METHOD - Add this for clear button functionality
    def clear_chat_history(self, user, problem):
        """Clear chat history for a problem - Required for clear button"""
        try:
            # Deactivate current conversation
            ChatConversation.objects.filter(
                user=user,
                problem=problem,
                is_active=True
            ).update(is_active=False)
            
            # Clear user progress
            UserProgress.objects.filter(
                user=user,
                problem=problem
            ).delete()
            
            logger.info(f"Chat history cleared for user {user.id} and problem {problem.id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")
            return False

    def get_conversation_summary(self, user, problem):
        """Get conversation summary"""
        try:
            conversation = ChatConversation.objects.filter(
                user=user, 
                problem=problem,
                is_active=True
            ).first()
            
            if not conversation:
                return None
            
            progress = UserProgress.objects.filter(user=user, problem=problem).first()
            message_count = conversation.messages.exclude(role='system').count()
            
            return {
                'total_messages': message_count,
                'hints_used': progress.hints_used if progress else 0,
                'stuck_count': progress.stuck_count if progress else 0,
                'approaches_discussed': progress.approaches_discussed if progress else [],
                'last_interaction': progress.last_hint_time if progress else conversation.updated_at
            }
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return None

    # ✅ BONUS: Add chat history retrieval method for completeness
    def get_chat_history(self, user, problem):
        """Get chat history as a list for frontend display"""
        try:
            conversation = ChatConversation.objects.filter(
                user=user, 
                problem=problem, 
                is_active=True
            ).first()
            
            if not conversation:
                return []

            messages = conversation.messages.exclude(role='system').order_by('timestamp')
            history = []
            
            for msg in messages:
                history.append({
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                })
            
            return history
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
