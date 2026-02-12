# Application to get HTML content of a book

# Objectives
- Get the HTML content of a book 
- The content requires javasscript client side rendering, so we will use Selenium to get the content
- it should be a cli tool with no user interface, just a command line tool to get the content of a book
- Save the HTML content to a file

# Usage

```text
usage: dget [-h] -o OUTPUT [--timeout TIMEOUT] [--user-agent USER_AGENT]
            [--min-text-chars MIN_TEXT_CHARS] [--format {html,text}]
            url
```

# Example

### URL

<https://reader.dia.hu/document/Krasznahorkai_Laszlo-Az_ellenallas_melankoliaja-1083>

### Text excerpt

```text
Krasznahorkai László
Az ellenállás melankóliája
Digitális Irodalmi Akadémia
© Petőfi Irodalmi Múzeum • Budapest • 2011

Az ellenállás melankóliája

Telik, de nem múlik.

Rendkívüli állapotok

Bevezetés

Minthogy a fagyba dermedt dél-alföldi településeket a Tiszától majdnem a Kárpátok lábáig összekötő személyvonat a sínek mentén tanácstalanul őgyelgő vasutas zavaros magyarázatai s a peronra idegesen ki-kiszaladó állomásfőnök egyre határozottabb ígéretei ellenére sem érkezett meg („Hát, kérem, ez megint fölszívódott…” – legyintett kajánul savanyú képpel a vasutas), a mindössze két, csupán efféle,
```

# Implementation 
- We will use Selenium with a headless browser to get the content of the book 
- We will use argparse to parse the command line arguments 
- We will save the HTML content to a file specified by the user 
- Add error handling and logging for better debugging and user experience

# Future Improvements 
- Add support for other websites that require javascript rendering 
- Add support for converting the HTML content to other formats like EPUB 

# Conclusion 

This application will allow users to easily get the HTML content of a book from a website that requires javascript rendering. It will be a useful tool for researchers, students, and anyone who wants to access the content of a book in a convenient way.
