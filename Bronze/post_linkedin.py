from integrations.social.linkedin import LinkedInPlatform

# Change this to your post text
POST_TEXT = "Hello from AI Employee! #automation #AI"

li = LinkedInPlatform()
result = li.post(POST_TEXT)

print("Success:", result.success)
if result.error:
    print("Error:", result.error)
else:
    print("Posted successfully!")
