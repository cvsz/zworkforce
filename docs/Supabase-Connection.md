# Connect to your project
# Choose how you want to use Supabase

1. Install packages
Run this command to install the required dependencies.
Code:
File: Code
```
npm install @supabase/supabase-js @supabase/ssr
```

2. Add Supabase Library blocks
Install Supabase Library blocks via the shadcn registry.
Details:
Add UI components for auth, realtime, storage, and more at supabase.com/library.
Code:
File: Code
```
npx shadcn@latest add @supabase/supabase-client-nextjs
```

3. Set env variables
Add the following values to your env file.
Code:
File: .env.local
```
NEXT_PUBLIC_SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

4. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install package
Run this command to install the required dependencies.
Code:
File: Code
```
npm install @supabase/supabase-js
```

2. Add Supabase Library blocks
Install Supabase Library blocks via the shadcn registry.
Details:
Add UI components for auth, realtime, storage, and more at supabase.com/library.
Code:
File: Code
```
npx shadcn@latest add @supabase/supabase-client-nextjs
```

3. Set env variables
Add the following values to your env file.
Code:
File: .env.local
```
NEXT_PUBLIC_SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

4. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install package
Run this command to install the required dependencies.
Code:
File: Code
```
npm install @supabase/supabase-js
```

2. Add Supabase Library blocks
Install Supabase Library blocks via the shadcn registry.
Details:
Add UI components for auth, realtime, storage, and more at supabase.com/library.
Code:
File: Code
```
npx shadcn@latest add @supabase/supabase-client-react-router
```

3. Set env variables
Add the following values to your env file.
Code:
File: .env
```
VITE_SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

4. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install packages
Run this command to install the required dependencies.
Code:
File: Code
```
npm install @supabase/supabase-js @supabase/ssr
```

2. Add files
Copy the following code into your project.
Code:
File: .env
```
VITE_SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

File: app/utils/supabase.server.ts
```
1import {
2  createServerClient,
3  parseCookieHeader,
4  serializeCookieHeader,
5} from "@supabase/ssr";
6
7export function createClient(request: Request) {
8  const headers = new Headers();
9
10  const supabase = createServerClient(
11    process.env.VITE_SUPABASE_URL!,
12    process.env.VITE_SUPABASE_PUBLISHABLE_KEY!,
13    {
14      cookies: {
15        getAll() {
16          return parseCookieHeader(request.headers.get("Cookie") ?? "") as {
17            name: string;
18            value: string;
19          }[];
20        },
21        setAll(cookiesToSet) {
22          cookiesToSet.forEach(({ name, value, options }) =>
23            headers.append(
24              "Set-Cookie",
25              serializeCookieHeader(name, value, options)
26            )
27          );
28        },
29      },
30    }
31  );
32
33  return { supabase, headers };
34}
```

File: app/routes/_index.tsx
```
1import type { Route } from "./+types/home";
2import { createClient } from "~/utils/supabase.server";
3
4export async function loader({ request }: Route.LoaderArgs) {
5  const { supabase } = createClient(request);
6  const { data: todos } = await supabase.from("todos").select();
7
8  return { todos };
9}
10
11export default function Home({ loaderData }: Route.ComponentProps) {
12  return (
13    <>
14      <ul>
15        {loaderData.todos?.map((todo) => (
16          <li key={todo.id}>{todo.name}</li>
17        ))}
18      </ul>
19    </>
20  );
21}
```

3. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install package
Run this command to install the required dependencies.
Code:
File: Code
```
npm install @supabase/supabase-js
```

2. Add Supabase Library blocks
Install Supabase Library blocks via the shadcn registry.
Details:
Add UI components for auth, realtime, storage, and more at supabase.com/library.
Code:
File: Code
```
npx shadcn@latest add @supabase/supabase-client-react-router
```

3. Set env variables
Add the following values to your env file.
Code:
File: .env.local
```
REACT_APP_SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
REACT_APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

4. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install package
Run this command to install the required dependencies.
Code:
File: Code
```
pip install supabase
```

2. Add files
Copy the following code into your project.
Code:
File: .env
```
SUPABASE_URL=https://aqbtiobrpwstjbbwtqap.supabase.co
SUPABASE_KEY=sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45
```

File: app.py
```
1import os
2from flask import Flask
3from supabase import create_client, Client
4from dotenv import load_dotenv
5
6load_dotenv()
7
8app = Flask(__name__)
9
10supabase: Client = create_client(
11    os.environ.get("SUPABASE_URL"),
12    os.environ.get("SUPABASE_KEY")
13)
14
15@app.route('/')
16def index():
17    response = supabase.table('todos').select("*").execute()
18    todos = response.data
19
20    html = '<h1>Todos</h1><ul>'
21    for todo in todos:
22        html += f'<li>{todo["name"]}</li>'
23    html += '</ul>'
24
25    return html
26
27if __name__ == '__main__':
28    app.run(debug=True)
```

3. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install packages
Run these commands to install the required dependencies.
Code:
File: Code
```
dotnet add package Supabase
dotnet add package Supabase.Extensions.DependencyInjection
```

2. Add files
Copy the following code into your project.
Code:
File: appsettings.json
```
1{
2  "Supabase": {
3    "Url": "https://aqbtiobrpwstjbbwtqap.supabase.co",
4    "Key": "sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45"
5  }
6}
```

File: Program.cs
```
1using Supabase.Extensions.DependencyInjection;
2
3var builder = WebApplication.CreateBuilder(args);
4
5// Registers Supabase.Client and each of its sub-clients (Auth, Postgrest,
6// Storage, Functions, Realtime) in the DI container, backed by pooled
7// HttpClients from IHttpClientFactory.
8//
9// Blazor registers the client the same way: use this in your Blazor Server /
10// Web App Program.cs, or WebAssemblyHostBuilder.CreateDefault(args) for a
11// Blazor WebAssembly client.
12builder.Services.AddSupabase(
13    builder.Configuration["Supabase:Url"]!,
14    builder.Configuration["Supabase:Key"]!
15);
16
17var app = builder.Build();
18
19// Inject Supabase.Client (or a single sub-client) wherever you need it — a
20// minimal API endpoint here, or a @inject in a Blazor component.
21app.MapGet("/todos", async (Supabase.Client supabase) =>
22{
23    await supabase.InitializeAsync();
24    var response = await supabase.From<Todo>().Get();
25    return response.Models;
26});
27
28app.Run();
```

File: Models/Todo.cs
```
1using Supabase.Postgrest.Attributes;
2using Supabase.Postgrest.Models;
3
4[Table("todos")]
5public class Todo : BaseModel
6{
7    [PrimaryKey("id")]
8    public long Id { get; set; }
9
10    [Column("name")]
11    public string Name { get; set; } = string.Empty;
12}
```

3. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------

1. Install package
Run this command to install the required dependencies.
Code:
File: Code
```
dotnet add package Supabase
```

2. Add files
Copy the following code into your project.
Code:
File: Program.cs
```
1using Supabase;
2
3var url = "https://aqbtiobrpwstjbbwtqap.supabase.co";
4var key = "sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45";
5
6var supabase = new Client(url, key, new SupabaseOptions
7{
8    AutoConnectRealtime = true
9});
10await supabase.InitializeAsync();
11
12var response = await supabase.From<Todo>().Get();
13foreach (var todo in response.Models)
14{
15    Console.WriteLine(todo.Name);
16}
```

File: Todo.cs
```
1using Supabase.Postgrest.Attributes;
2using Supabase.Postgrest.Models;
3
4[Table("todos")]
5public class Todo : BaseModel
6{
7    [PrimaryKey("id")]
8    public long Id { get; set; }
9
10    [Column("name")]
11    public string Name { get; set; } = string.Empty;
12}
```

3. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```

--------------------------------------------------------------------
# Unity

1. Install package
Add the Supabase SDK to your Unity project.
Details:
Unity resolves NuGet packages through NuGetForUnity. Install it from the Package Manager via Add package from git URL:
Then open Window → NuGet → Manage NuGet Packages, search for Supabase, and install it. If you build with IL2CPP, preserve your model types from managed code stripping with a link.xml.
Code:
File: Code
```
https://github.com/GlitchEnzo/NuGetForUnity.git?path=/src/NuGetForUnity
```

2. Add files
Copy the following code into your project.
Details:
Before running the sample, attach SupabaseManager to an active GameObject and attach TodoList to an active GameObject in the scene.
Code:
File: SupabaseManager.cs
```
1using System.Threading.Tasks;
2using Supabase;
3using UnityEngine;
4
5// Keep a single client alive for the whole game and expose it through a
6// MonoBehaviour singleton that survives scene loads.
7public class SupabaseManager : MonoBehaviour
8{
9    public static SupabaseManager Instance { get; private set; }
10    public Client Supabase { get; private set; }
11
12    // Await this before using the client. Awake returns at the first await, so
13    // other scripts could run before InitializeAsync() finishes without it.
14    public Task InitializationTask { get; private set; }
15
16    private const string Url = "https://aqbtiobrpwstjbbwtqap.supabase.co";
17    private const string Key = "sb_publishable_9KY5tw-0gdykBFpgjCfCoQ_H3cIAu45";
18
19    private void Awake()
20    {
21        if (Instance != null)
22        {
23            Destroy(gameObject);
24            return;
25        }
26
27        Instance = this;
28        DontDestroyOnLoad(gameObject);
29        InitializationTask = InitializeAsync();
30    }
31
32    private async Task InitializeAsync()
33    {
34        Supabase = new Client(Url, Key, new SupabaseOptions
35        {
36            AutoConnectRealtime = true
37        });
38        await Supabase.InitializeAsync();
39    }
40}
```

File: TodoList.cs
```
1using System.Threading.Tasks;
2using UnityEngine;
3
4public class TodoList : MonoBehaviour
5{
6    // Start() can't be awaited, so kick off the async work from a Task method.
7    private void Start()
8    {
9        _ = LoadTodosAsync();
10    }
11
12    private async Task LoadTodosAsync()
13    {
14        var manager = SupabaseManager.Instance;
15        await manager.InitializationTask;
16
17        var response = await manager.Supabase.From<Todo>().Get();
18        foreach (var todo in response.Models)
19        {
20            Debug.Log(todo.Name);
21        }
22    }
23}
```

File: Todo.cs
```
1using Supabase.Postgrest.Attributes;
2using Supabase.Postgrest.Models;
3
4[Table("todos")]
5public class Todo : BaseModel
6{
7    [PrimaryKey("id")]
8    public long Id { get; set; }
9
10    [Column("name")]
11    public string Name { get; set; } = string.Empty;
12}
```

3. Install Agent Skills (optional)
Agent Skills give AI coding tools ready-made instructions, scripts, and resources for working with Supabase more accurately and efficiently.
Code:
File: Code
```
npx skills add supabase/agent-skills
```
